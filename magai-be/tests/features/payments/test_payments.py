"""Payment flows: ownership, open-redirect guard, webhook verification."""

from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.features.payments.models import Payment, Subscription
from app.features.widgets.models import Widget


async def _widget(db, owner) -> Widget:
    widget = Widget(
        user_id=owner.id,
        target_url="https://example.com",
        widget_type="roi_calculator",
        title="Calc",
        status="active",
    )
    db.add(widget)
    await db.commit()
    await db.refresh(widget)
    return widget


class TestCreateCheckout:
    async def test_requires_authentication(self, client):
        response = await client.post(
            "/api/payments/create-checkout",
            json={
                "widget_id": "11111111-1111-1111-1111-111111111111",
                "success_url": "http://localhost:3000/ok",
                "cancel_url": "http://localhost:3000/no",
            },
        )
        assert response.status_code == 401

    async def test_cannot_pay_for_another_users_widget(self, as_user, db, user, other_user):
        widget = await _widget(db, user)
        response = await as_user(other_user).post(
            "/api/payments/create-checkout",
            json={
                "widget_id": str(widget.id),
                "success_url": "http://localhost:3000/ok",
                "cancel_url": "http://localhost:3000/no",
            },
        )
        assert response.status_code == 404

    async def test_offsite_redirect_url_is_rejected(self, as_user, db, user):
        widget = await _widget(db, user)
        # Otherwise this endpoint is an open redirect through a genuine Stripe flow.
        response = await as_user(user).post(
            "/api/payments/create-checkout",
            json={
                "widget_id": str(widget.id),
                "success_url": "https://evil.example/steal",
                "cancel_url": "http://localhost:3000/no",
            },
        )
        assert response.status_code == 422

    async def test_non_http_redirect_scheme_is_rejected(self, as_user, db, user):
        widget = await _widget(db, user)
        response = await as_user(user).post(
            "/api/payments/create-checkout",
            json={
                "widget_id": str(widget.id),
                "success_url": "javascript:alert(1)",
                "cancel_url": "http://localhost:3000/no",
            },
        )
        assert response.status_code == 422

    async def test_paying_twice_is_refused_without_calling_stripe(self, as_user, db, user):
        """The already-entitled guard has to run *before* the provider call.

        Creating a Stripe checkout session is an external side effect that the
        request's rollback cannot undo, so checking afterwards still left an
        orphan session in Stripe for every duplicate payment attempt.
        """
        widget = await _widget(db, user)
        widget.entitlement_status = "paid"
        await db.commit()

        with patch(
            "app.features.payments.routes.create_checkout_session",
            new_callable=AsyncMock,
            return_value=("https://checkout.stripe.test/x", "cs_test_x"),
        ) as create:
            response = await as_user(user).post(
                "/api/payments/create-checkout",
                json={
                    "widget_id": str(widget.id),
                    "success_url": "http://localhost:3000/ok",
                    "cancel_url": "http://localhost:3000/no",
                },
            )

        assert response.status_code == 409
        assert response.json()["detail"] == "widget_already_entitled"
        create.assert_not_called()


class TestWebhook:
    async def test_missing_signature_is_rejected(self, client):
        response = await client.post("/api/payments/stripe/webhook", content=b"{}")
        assert response.status_code == 400
        assert response.json()["detail"] == "missing_signature"

    async def test_invalid_signature_is_rejected(self, client):
        # Without signature verification anyone could mark payments as paid.
        response = await client.post(
            "/api/payments/stripe/webhook",
            content=b'{"type":"checkout.session.completed"}',
            headers={"Stripe-Signature": "t=1,v1=forged"},
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "invalid_signature"

    async def test_valid_signature_is_processed(self, client):
        event = {
            "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_test_123"}},
        }
        with (
            patch("stripe.Webhook.construct_event", return_value=event),
            patch(
                "app.features.payments.routes.handle_checkout_completed",
                new=AsyncMock(return_value=True),
            ) as handler,
        ):
            response = await client.post(
                "/api/payments/stripe/webhook",
                content=b"{}",
                headers={"Stripe-Signature": "t=1,v1=valid"},
            )

        assert response.status_code == 200
        handler.assert_awaited_once()

    async def test_unrelated_event_types_are_ignored(self, client):
        event = {"type": "invoice.paid", "data": {"object": {}}}
        with (
            patch("stripe.Webhook.construct_event", return_value=event),
            patch(
                "app.features.payments.routes.handle_checkout_completed", new=AsyncMock()
            ) as handler,
        ):
            response = await client.post(
                "/api/payments/stripe/webhook",
                content=b"{}",
                headers={"Stripe-Signature": "t=1,v1=valid"},
            )

        assert response.status_code == 200
        handler.assert_not_awaited()

    async def test_subscription_checkout_is_dispatched_to_subscription_handler(self, client):
        event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_subscription",
                    "metadata": {"kind": "workspace_subscription"},
                }
            },
        }
        with (
            patch("stripe.Webhook.construct_event", return_value=event),
            patch(
                "app.features.payments.routes.handle_subscription_checkout_completed",
                new=AsyncMock(return_value=True),
            ) as handler,
        ):
            response = await client.post(
                "/api/payments/stripe/webhook",
                content=b"{}",
                headers={"Stripe-Signature": "t=1,v1=valid"},
            )

        assert response.status_code == 200
        handler.assert_awaited_once()
        assert handler.await_args.args[1] == "cs_subscription"


class TestPaymentIdempotency:
    async def test_already_confirmed_payment_is_not_reprocessed(self, db, user):
        from app.features.payments.service import handle_checkout_completed

        payment = Payment(
            user_id=user.id,
            stripe_session_id="cs_test_dupe",
            amount=9900,
            currency="usd",
            status="confirmed",
        )
        db.add(payment)
        await db.commit()

        # Stripe retries webhooks; a replay must not double-process.
        with patch("stripe.checkout.Session.retrieve") as retrieve:
            result = await handle_checkout_completed(db, "cs_test_dupe")

        assert result is True
        retrieve.assert_not_called()

    async def test_unknown_session_is_reported_as_unhandled(self, db):
        from app.features.payments.service import handle_checkout_completed

        assert await handle_checkout_completed(db, "cs_never_seen") is False

    async def test_confirmed_payment_unlocks_its_widget(self, db, user):
        from app.features.payments.service import handle_checkout_completed
        from app.platform.config.settings import settings

        widget = await _widget(db, user)
        widget.entitlement_status = "checkout_pending"
        payment = Payment(
            user_id=user.id,
            widget_id=widget.id,
            stripe_session_id="cs_unlock",
            amount=settings.widget_launch_price_cents,
            currency=settings.widget_launch_currency,
            status="pending",
        )
        db.add(payment)
        await db.commit()

        class PaidSession:
            payment_status = "paid"
            payment_intent = "pi_unlock"

            @staticmethod
            def get(key):
                return settings.widget_launch_price_cents if key == "amount_total" else None

        with patch("stripe.checkout.Session.retrieve", return_value=PaidSession()):
            assert await handle_checkout_completed(db, "cs_unlock") is True
        await db.commit()
        await db.refresh(widget)
        assert widget.entitlement_status == "paid"


class TestListPayments:
    async def test_only_own_payments_are_listed(self, as_user, db, user, other_user):
        db.add(
            Payment(
                user_id=user.id,
                stripe_session_id="cs_owner",
                amount=9900,
                currency="usd",
                status="confirmed",
            )
        )
        await db.commit()

        response = await as_user(other_user).get("/api/payments")
        assert response.status_code == 200
        assert response.json() == []


class TestWorkspaceSubscriptions:
    async def test_free_workspace_status_is_explicit(self, as_user, user):
        response = await as_user(user).get("/api/payments/subscription")

        assert response.status_code == 200
        assert response.json() == {
            "plan": "free",
            "status": "free",
            "active_experiences": 0,
            "experience_limit": 0,
            "monthly_price": 0,
            "currency": "usd",
            "current_period_end": None,
        }

    async def test_checkout_creates_pending_workspace_subscription(self, as_user, db, user):
        class Checkout:
            id = "cs_workspace"
            url = "https://checkout.stripe.com/c/pay/cs_workspace"

        with patch("stripe.checkout.Session.create", return_value=Checkout()) as create:
            response = await as_user(user).post(
                "/api/payments/create-subscription-checkout",
                json={
                    "plan": "studio",
                    "success_url": "http://localhost:3000/dashboard/settings?checkout=success",
                    "cancel_url": "http://localhost:3000/dashboard/settings",
                },
            )

        assert response.status_code == 200
        assert create.call_args.kwargs["mode"] == "subscription"
        assert create.call_args.kwargs["line_items"][0]["price_data"]["recurring"] == {
            "interval": "month"
        }
        subscription = await db.scalar(select(Subscription).where(Subscription.user_id == user.id))
        assert subscription is not None
        assert subscription.plan == "studio"
        assert subscription.status == "checkout_pending"

    async def test_active_subscription_unlocks_builds_up_to_plan_limit(self, db, user, monkeypatch):
        from app.features.widgets.service import account_can_build
        from app.platform.config.settings import settings

        monkeypatch.setattr(settings, "require_payment_to_build", True)
        subscription = Subscription(user_id=user.id, plan="studio", status="active")
        candidate = Widget(
            user_id=user.id,
            target_url="https://candidate.example",
            widget_type="audit_tool",
            title="Candidate",
            status="analyzed",
            entitlement_status="preview",
        )
        db.add_all([subscription, candidate])
        await db.commit()

        assert await account_can_build(db, candidate) is True

        for index in range(settings.studio_active_experience_limit):
            db.add(
                Widget(
                    user_id=user.id,
                    target_url=f"https://live-{index}.example",
                    widget_type="audit_tool",
                    title=f"Live {index}",
                    status="active",
                )
            )
        await db.commit()

        assert await account_can_build(db, candidate) is False
