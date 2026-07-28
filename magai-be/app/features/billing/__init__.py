"""What a workspace is allowed to do, and how much of it is left.

Deliberately separate from ``payments``, which owns money movement (Stripe
sessions, webhooks, the ``Subscription`` row). This package owns the *product*
question — which features are on, which caps apply, how much of each has been
used — so a screen can ask "may I?" without knowing anything about billing.
"""
