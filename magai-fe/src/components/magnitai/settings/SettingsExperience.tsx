import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Bell,
  BookOpen,
  Building2,
  Check,
  CheckCircle2,
  Copy,
  CreditCard,
  Database,
  Download,
  FlaskConical,
  Globe2,
  KeyRound,
  LifeBuoy,
  Link2,
  Loader2,
  Mail,
  MessageCircle,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Trash2,
  UserRound,
  UsersRound,
  type LucideIcon,
} from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import {
  api,
  useAcceptTeamInvitation,
  useApiKeys,
  useChangePassword,
  useConfirmMfa,
  useCreateApiKey,
  useCreateCustomDomain,
  useCreateSubscriptionCheckout,
  useCustomDomains,
  useDeleteAccount,
  useDeleteCustomDomain,
  useDisableMfa,
  useEnrollMfa,
  useEntitlements,
  useInviteTeamMember,
  useMfaStatus,
  usePlans,
  useRemoveTeamMember,
  useRevokeApiKey,
  useRevokeTeamInvitation,
  useTeam,
  useUpdateLabs,
  useUpdateNotifications,
  useUpdateProfile,
  useUpdateWorkspace,
  useVerifyCustomDomain,
  useWidgets,
  type CreatedWorkspaceApiKey,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatPrice, UpgradeNotice, UsageMeter, useGate } from "@/lib/plan";

const INPUT =
  "h-11 w-full rounded-lg border border-border bg-card px-3 text-sm text-foreground outline-none transition-colors placeholder:text-n-400 focus:border-foreground/40 focus:ring-2 focus:ring-ring/20";

const SELECT = `${INPUT} appearance-none`;

type SettingId =
  | "profile"
  | "workspace"
  | "billing"
  | "domains"
  | "notifications"
  | "api-keys"
  | "team"
  | "security"
  | "data"
  | "labs";

interface SettingDefinition {
  id: SettingId;
  title: string;
  description: string;
  icon: LucideIcon;
  badge?: "Pro" | "Beta";
}

const SETTINGS: SettingDefinition[] = [
  {
    id: "profile",
    title: "Profile",
    description: "Manage your personal details, email and password.",
    icon: UserRound,
  },
  {
    id: "workspace",
    title: "Workspace",
    description: "Update your workspace name, timezone and brand defaults.",
    icon: Building2,
  },
  {
    id: "billing",
    title: "Billing & plan",
    description: "Review your plan, usage, renewal and available upgrades.",
    icon: CreditCard,
  },
  {
    id: "domains",
    title: "Domains",
    description: "Connect a branded domain to any published tool.",
    icon: Globe2,
    badge: "Pro",
  },
  {
    id: "notifications",
    title: "Notifications",
    description: "Choose which workspace updates reach your inbox.",
    icon: Bell,
  },
  {
    id: "api-keys",
    title: "API keys",
    description: "Create and revoke secure keys for your own systems.",
    icon: KeyRound,
    badge: "Pro",
  },
  {
    id: "team",
    title: "Team",
    description: "Invite collaborators and manage workspace access.",
    icon: UsersRound,
  },
  {
    id: "security",
    title: "Security",
    description: "Manage two-factor authentication and account protection.",
    icon: ShieldCheck,
  },
  {
    id: "data",
    title: "Data & export",
    description: "Download a portable copy or permanently delete your data.",
    icon: Download,
  },
  {
    id: "labs",
    title: "Labs",
    description: "Opt in to carefully released experimental improvements.",
    icon: FlaskConical,
    badge: "Beta",
  },
];

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-foreground">{label}</span>
      {children}
      {hint && <span className="mt-1.5 block text-xs leading-5 text-muted-foreground">{hint}</span>}
    </label>
  );
}

function Toggle({
  id,
  checked,
  disabled = false,
  onChange,
  label,
  hint,
}: {
  id: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (next: boolean) => void;
  label: string;
  hint: string;
}) {
  return (
    <div className="flex items-start justify-between gap-6 py-1">
      <div className="min-w-0">
        <label htmlFor={id} className="text-sm font-medium text-foreground">
          {label}
        </label>
        <p className="mt-1 max-w-xl text-sm leading-6 text-muted-foreground">{hint}</p>
      </div>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`relative mt-0.5 h-7 w-12 shrink-0 rounded-full transition-colors disabled:opacity-50 ${
          checked ? "bg-foreground" : "bg-n-300"
        }`}
      >
        <span
          className={`absolute top-1 size-5 rounded-full bg-card shadow-raised transition-transform ${
            checked ? "translate-x-6" : "translate-x-1"
          }`}
        />
      </button>
    </div>
  );
}

function Panel({
  title,
  description,
  children,
  className = "",
}: {
  title?: string;
  description?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`surface p-5 sm:p-6 ${className}`}>
      {title && <h2 className="text-base font-medium text-foreground">{title}</h2>}
      {description && <p className="mt-1 text-sm leading-6 text-muted-foreground">{description}</p>}
      <div className={title || description ? "mt-5" : ""}>{children}</div>
    </section>
  );
}

function ErrorMessage({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <p role="alert" className="mt-3 text-sm text-destructive">
      {(error as Error).message}
    </p>
  );
}

function SaveButton({
  pending,
  saved,
  children = "Save changes",
}: {
  pending: boolean;
  saved: boolean;
  children?: ReactNode;
}) {
  return (
    <div className="flex items-center gap-3">
      <button type="submit" disabled={pending} className="btn btn-primary h-10 text-sm">
        {pending && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
        {children}
      </button>
      <span
        aria-live="polite"
        className={`flex items-center gap-1.5 text-sm text-success transition-opacity ${
          saved ? "opacity-100" : "opacity-0"
        }`}
      >
        <Check className="size-4" aria-hidden="true" />
        Saved
      </span>
    </div>
  );
}

function SettingCard({ setting }: { setting: SettingDefinition }) {
  const Icon = setting.icon;
  return (
    <li>
      <Link
        to="/dashboard/settings"
        hash={setting.id}
        activeOptions={{ exact: true, includeHash: true }}
        className="group flex min-h-28 items-center gap-4 rounded-[--radius-surface] border border-border bg-card p-5 shadow-soft transition-[border-color,box-shadow,transform] hover:-translate-y-0.5 hover:border-border-strong hover:shadow-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-secondary">
          <Icon className="size-5 text-foreground" aria-hidden="true" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2">
            <span className="text-[15px] font-medium text-foreground">{setting.title}</span>
            {setting.badge && (
              <span
                className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                  setting.badge === "Beta"
                    ? "bg-secondary text-muted-foreground"
                    : "bg-brand-wash text-brand-solid"
                }`}
              >
                {setting.badge}
              </span>
            )}
          </span>
          <span className="mt-1 block max-w-[26rem] text-sm leading-5 text-muted-foreground">
            {setting.description}
          </span>
        </span>
        <ArrowRight
          className="size-4 shrink-0 text-n-400 transition-transform group-hover:translate-x-0.5 group-hover:text-foreground"
          aria-hidden="true"
        />
      </Link>
    </li>
  );
}

function SupportRail() {
  const { data: health, isError } = useQuery<{ status: "ok" | "degraded" }>({
    queryKey: ["system-health"],
    queryFn: () => api.get("/health"),
    staleTime: 60_000,
    retry: 1,
  });
  const operational = health?.status === "ok";

  return (
    <aside className="surface overflow-hidden lg:sticky lg:top-24">
      <div className="border-b border-border bg-[linear-gradient(145deg,var(--card),var(--secondary))] p-6">
        <span className="grid size-10 place-items-center rounded-xl bg-card shadow-soft">
          <Sparkles className="size-4 text-foreground" aria-hidden="true" />
        </span>
        <h2 className="mt-5 font-serif text-2xl tracking-[-0.025em] text-foreground">
          Need a hand?
        </h2>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          Tell us what you are trying to set up and include the tool name if one is involved.
        </p>
        <a
          href="mailto:support@magnitai.com?subject=Magnitai%20settings%20help"
          className="btn btn-primary mt-5 h-10 w-full text-sm"
        >
          <MessageCircle className="size-4" aria-hidden="true" />
          Contact support
        </a>
        <p className="mt-2.5 flex items-center justify-center gap-2 text-xs text-muted-foreground">
          <span
            className={`size-2 rounded-full ${
              operational
                ? "bg-success"
                : isError || health?.status === "degraded"
                  ? "bg-warning"
                  : "bg-n-300"
            }`}
            aria-hidden="true"
          />
          {operational
            ? "All systems operational"
            : isError || health?.status === "degraded"
              ? "Service status needs attention"
              : "Checking service status"}
        </p>
      </div>

      <div className="p-6">
        <h3 className="text-sm font-medium text-foreground">Help & resources</h3>
        <nav aria-label="Settings help" className="mt-3">
          <ul className="space-y-1">
            {[
              {
                icon: BookOpen,
                label: "Help center",
                detail: "Guides for building and publishing",
                to: "/dashboard/help",
              },
              {
                icon: Link2,
                label: "Integrations",
                detail: "Connect lead delivery",
                to: "/dashboard/integrations",
              },
              {
                icon: Building2,
                label: "Brand workspace",
                detail: "Set shared visual defaults",
                to: "/dashboard/brand",
              },
            ].map((item) => {
              const Icon = item.icon;
              return (
                <li key={item.label}>
                  <Link
                    to={item.to}
                    className="group flex items-start gap-3 rounded-lg px-2 py-2.5 transition-colors hover:bg-n-50"
                  >
                    <Icon
                      className="mt-0.5 size-4 shrink-0 text-muted-foreground"
                      aria-hidden="true"
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-medium text-foreground">
                        {item.label}
                      </span>
                      <span className="mt-0.5 block text-xs leading-5 text-muted-foreground">
                        {item.detail}
                      </span>
                    </span>
                    <ArrowRight
                      className="mt-1 size-3.5 text-n-400 group-hover:text-foreground"
                      aria-hidden="true"
                    />
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>

      <div className="mx-6 mb-6 rounded-xl border border-border bg-n-50 p-4">
        <div className="flex items-start gap-3">
          <span className="grid size-9 shrink-0 place-items-center rounded-full bg-brand-wash">
            <Mail className="size-4 text-brand-solid" aria-hidden="true" />
          </span>
          <div>
            <h3 className="text-sm font-medium text-foreground">We value useful feedback</h3>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">
              Tell us what made a setting hard to find or understand.
            </p>
            <a
              href="mailto:feedback@magnitai.com?subject=Settings%20feedback"
              className="mt-2.5 inline-flex text-xs font-medium text-foreground underline underline-offset-2"
            >
              Share feedback
            </a>
          </div>
        </div>
      </div>
    </aside>
  );
}

function SettingsHome() {
  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <ul className="grid gap-4 sm:grid-cols-2">
        {SETTINGS.map((setting) => (
          <SettingCard key={setting.id} setting={setting} />
        ))}
      </ul>
      <SupportRail />
    </div>
  );
}

function DetailHeader({ setting }: { setting: SettingDefinition }) {
  const Icon = setting.icon;
  return (
    <header className="mb-6">
      <Link
        to="/dashboard/settings"
        hash=""
        className="mb-4 inline-flex min-h-9 items-center gap-2 rounded-lg pr-2 text-sm font-medium text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden="true" />
        All settings
      </Link>
      <div className="flex items-start gap-4">
        <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-secondary">
          <Icon className="size-5" aria-hidden="true" />
        </span>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-medium tracking-[-0.025em] text-foreground">
              {setting.title}
            </h1>
            {setting.badge && (
              <span className="rounded-full bg-brand-wash px-2 py-0.5 text-[10px] font-medium text-brand-solid">
                {setting.badge}
              </span>
            )}
          </div>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
            {setting.description}
          </p>
        </div>
      </div>
    </header>
  );
}

function ProfilePanel() {
  const { user } = useAuth();
  const update = useUpdateProfile();
  const [name, setName] = useState(user?.display_name ?? "");

  if (!user) return null;

  return (
    <div className="space-y-5">
      <Panel title="Personal details" description="Used to identify you to teammates and support.">
        <form
          className="max-w-lg space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            update.mutate({ display_name: name.trim() || null });
          }}
        >
          <Field label="Display name">
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              autoComplete="name"
              placeholder="Your name"
              className={INPUT}
            />
          </Field>
          <Field label="Email address" hint="Your sign-in email is also used for account notices.">
            <input
              value={user.email}
              readOnly
              className={`${INPUT} bg-n-50 text-muted-foreground`}
            />
          </Field>
          <SaveButton pending={update.isPending} saved={update.isSuccess} />
          <ErrorMessage error={update.error} />
        </form>
      </Panel>

      <Panel title="Account history">
        <dl className="grid gap-4 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-muted-foreground">Email status</dt>
            <dd className="mt-1 flex items-center gap-1.5 font-medium text-foreground">
              {user.email_verified ? (
                <>
                  <CheckCircle2 className="size-4 text-success" aria-hidden="true" />
                  Confirmed
                </>
              ) : (
                "Not confirmed"
              )}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Member since</dt>
            <dd className="mt-1 font-medium text-foreground">
              {new Date(user.created_at).toLocaleDateString(undefined, {
                year: "numeric",
                month: "long",
                day: "numeric",
              })}
            </dd>
          </div>
        </dl>
      </Panel>
      <ChangePassword />
    </div>
  );
}

function ChangePassword() {
  const mutation = useChangePassword();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");

  return (
    <Panel title="Password" description="Use at least 12 characters and avoid a reused password.">
      <form
        className="grid max-w-lg gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          mutation.mutate(
            { currentPassword: current, newPassword: next },
            {
              onSuccess: () => {
                setCurrent("");
                setNext("");
              },
            },
          );
        }}
      >
        <Field label="Current password">
          <input
            type="password"
            autoComplete="current-password"
            value={current}
            onChange={(event) => setCurrent(event.target.value)}
            className={INPUT}
          />
        </Field>
        <Field label="New password">
          <input
            type="password"
            autoComplete="new-password"
            value={next}
            onChange={(event) => setNext(event.target.value)}
            className={INPUT}
          />
        </Field>
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={mutation.isPending || !current || !next}
            className="btn btn-primary h-10 text-sm"
          >
            {mutation.isPending && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
            Update password
          </button>
          {mutation.isSuccess && (
            <span aria-live="polite" className="flex items-center gap-1.5 text-sm text-success">
              <Check className="size-4" aria-hidden="true" />
              Updated
            </span>
          )}
        </div>
        <ErrorMessage error={mutation.error} />
      </form>
    </Panel>
  );
}

function WorkspacePanel() {
  const { user } = useAuth();
  const mutation = useUpdateWorkspace();
  const [name, setName] = useState(user?.workspace_name ?? "");
  const [timezone, setTimezone] = useState(user?.workspace_timezone ?? "UTC");
  const timezones = useMemo(() => {
    const intl = Intl as typeof Intl & { supportedValuesOf?: (key: "timeZone") => string[] };
    return intl.supportedValuesOf?.("timeZone") ?? [timezone, "UTC"];
  }, [timezone]);

  if (!user) return null;

  return (
    <div className="space-y-5">
      <Panel
        title="Workspace details"
        description="Shared context for everyone who joins this workspace."
      >
        <form
          className="max-w-lg space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            mutation.mutate({ name: name.trim(), timezone });
          }}
        >
          <Field label="Workspace name">
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
              minLength={2}
              className={INPUT}
            />
          </Field>
          <Field
            label="Timezone"
            hint="Used when Magnitai displays reporting periods, invitations and activity times."
          >
            <input
              value={timezone}
              onChange={(event) => setTimezone(event.target.value)}
              list="workspace-timezones"
              required
              className={INPUT}
            />
            <datalist id="workspace-timezones">
              {timezones.map((zone) => (
                <option key={zone} value={zone} />
              ))}
            </datalist>
          </Field>
          <SaveButton pending={mutation.isPending} saved={mutation.isSuccess} />
          <ErrorMessage error={mutation.error} />
        </form>
      </Panel>
      <Panel
        title="Workspace brand"
        description="Set the colours, typography, logo and tone every new tool should inherit."
      >
        <Link to="/dashboard/brand" className="btn btn-secondary h-10 text-sm">
          <Building2 className="size-4" aria-hidden="true" />
          Open brand workspace
          <ArrowRight className="size-4" aria-hidden="true" />
        </Link>
      </Panel>
    </div>
  );
}

function BillingPanel() {
  const { data: entitlements, isLoading } = useEntitlements();
  const { data: catalog } = usePlans();
  const subscribe = useCreateSubscriptionCheckout();

  if (isLoading || !entitlements) {
    return (
      <Panel>
        <Loader2 className="size-5 animate-spin text-muted-foreground" aria-label="Loading plan" />
      </Panel>
    );
  }

  const plans = catalog?.plans ?? [];
  const currentIndex = plans.findIndex((plan) => plan.id === entitlements.plan.id);
  const upgrades =
    currentIndex >= 0 ? plans.slice(currentIndex + 1) : plans.filter((plan) => plan.purchasable);

  return (
    <div className="space-y-5">
      <Panel>
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div>
            <span className="text-sm text-muted-foreground">Current plan</span>
            <h2 className="mt-1 text-2xl font-medium tracking-[-0.025em] text-foreground">
              {entitlements.plan.name}
            </h2>
            {entitlements.current_period_end && (
              <p className="mt-1 text-sm text-muted-foreground">
                Renews{" "}
                {new Date(entitlements.current_period_end).toLocaleDateString(undefined, {
                  year: "numeric",
                  month: "long",
                  day: "numeric",
                })}
              </p>
            )}
            {entitlements.status === "past_due" && (
              <p className="mt-2 flex items-center gap-2 text-sm text-warning">
                <AlertTriangle className="size-4" aria-hidden="true" />
                The last payment failed. Your published tools stay live while billing retries.
              </p>
            )}
          </div>
          <div className="text-right">
            <span className="text-sm text-muted-foreground">Monthly</span>
            <strong className="mt-1 block text-2xl font-medium text-foreground">
              {formatPrice(entitlements.plan.monthly_price, entitlements.plan.currency)}
            </strong>
          </div>
        </div>
        <div className="mt-6 grid gap-5 border-t border-border pt-5 sm:grid-cols-2">
          <UsageMeter
            label="Live tools"
            used={entitlements.usage.live_tools}
            limit={entitlements.plan.live_tool_limit}
          />
          <UsageMeter
            label="Builds this month"
            used={entitlements.usage.builds_this_period}
            limit={entitlements.plan.monthly_build_limit}
          />
        </div>
      </Panel>

      {upgrades.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2">
          {upgrades.map((plan, index) => (
            <Panel key={plan.id} className={index === 0 ? "border-foreground" : ""}>
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-base font-medium text-foreground">{plan.name}</h2>
                {index === 0 && (
                  <span className="rounded-full bg-brand-wash px-2 py-0.5 text-[10px] font-medium text-brand-solid">
                    Recommended
                  </span>
                )}
              </div>
              <p className="mt-2 text-2xl font-medium tracking-[-0.03em] text-foreground">
                {formatPrice(plan.monthly_price, plan.currency)}
                <span className="ml-1 text-sm font-normal text-muted-foreground">/ month</span>
              </p>
              <ul className="mt-4 space-y-2">
                {plan.highlights.map((highlight) => (
                  <li
                    key={highlight}
                    className="flex items-start gap-2 text-sm text-muted-foreground"
                  >
                    <Check className="mt-0.5 size-4 shrink-0 text-success" aria-hidden="true" />
                    {highlight}
                  </li>
                ))}
              </ul>
              <button
                type="button"
                disabled={subscribe.isPending}
                onClick={() =>
                  subscribe.mutate(
                    {
                      plan: plan.id as "studio" | "scale",
                      successUrl: `${window.location.origin}/dashboard/settings#billing`,
                      cancelUrl: `${window.location.origin}/dashboard/settings#billing`,
                    },
                    {
                      onSuccess: (response) => window.location.assign(response.checkout_url),
                    },
                  )
                }
                className={`btn mt-5 h-10 w-full text-sm ${
                  index === 0 ? "btn-primary" : "btn-secondary"
                }`}
              >
                {subscribe.isPending && (
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                )}
                Choose {plan.name}
              </button>
            </Panel>
          ))}
        </div>
      )}
      <ErrorMessage error={subscribe.error} />
    </div>
  );
}

function NotificationsPanel() {
  const { user } = useAuth();
  const mutation = useUpdateNotifications();
  if (!user) return null;

  const update = (values: Parameters<typeof mutation.mutate>[0]) => mutation.mutate(values);

  return (
    <Panel
      title="Email notifications"
      description="Each switch saves to your account immediately. Teammates control their own inbox."
    >
      <div className="divide-y divide-border">
        <div className="pb-5">
          <Toggle
            id="notify-leads"
            checked={user.notify_on_lead}
            disabled={mutation.isPending}
            onChange={(checked) => update({ notify_on_lead: checked })}
            label="New lead alerts"
            hint="Email me when someone leaves their details in one of our tools."
          />
        </div>
        <div className="py-5">
          <Toggle
            id="notify-summary"
            checked={user.notify_weekly_summary}
            disabled={mutation.isPending}
            onChange={(checked) => update({ notify_weekly_summary: checked })}
            label="Weekly workspace summary"
            hint="A concise weekly view of traffic, completions, leads and tool health."
          />
        </div>
        <div className="pt-5">
          <Toggle
            id="notify-product"
            checked={user.notify_product_updates}
            disabled={mutation.isPending}
            onChange={(checked) => update({ notify_product_updates: checked })}
            label="Product updates"
            hint="Occasional notes about meaningful new capabilities. No promotional email."
          />
        </div>
      </div>
      <div aria-live="polite" className="mt-4 min-h-5 text-sm">
        {mutation.isPending && (
          <span className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            Saving
          </span>
        )}
        {mutation.isSuccess && (
          <span className="flex items-center gap-2 text-success">
            <Check className="size-4" aria-hidden="true" />
            Saved
          </span>
        )}
      </div>
      <ErrorMessage error={mutation.error} />
    </Panel>
  );
}

function DomainsPanel() {
  const gate = useGate("custom_domains");
  const { data: widgetsData } = useWidgets();
  const { data, isLoading } = useCustomDomains();
  const create = useCreateCustomDomain();
  const verify = useVerifyCustomDomain();
  const remove = useDeleteCustomDomain();
  const [hostname, setHostname] = useState("");
  const [widgetId, setWidgetId] = useState("");

  if (gate.loading) return null;
  if (!gate.allowed) return <UpgradeNotice feature="custom_domains" />;

  const published = (widgetsData?.widgets ?? []).filter((widget) => widget.deployment_url);

  return (
    <div className="space-y-5">
      <Panel
        title="Connect a domain"
        description="Choose a published tool, add a hostname, then follow the exact DNS records returned by the deployment provider."
      >
        {published.length ? (
          <form
            className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] md:items-end"
            onSubmit={(event) => {
              event.preventDefault();
              create.mutate(
                { widget_id: widgetId, hostname },
                {
                  onSuccess: () => {
                    setHostname("");
                    setWidgetId("");
                  },
                },
              );
            }}
          >
            <Field label="Published tool">
              <select
                value={widgetId}
                onChange={(event) => setWidgetId(event.target.value)}
                required
                className={SELECT}
              >
                <option value="">Choose a tool</option>
                {published.map((widget) => (
                  <option key={widget.id} value={widget.id}>
                    {widget.title}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Domain">
              <input
                value={hostname}
                onChange={(event) => setHostname(event.target.value)}
                placeholder="tools.example.com"
                inputMode="url"
                required
                className={INPUT}
              />
            </Field>
            <button
              type="submit"
              disabled={create.isPending || !widgetId || !hostname.trim()}
              className="btn btn-primary h-11 text-sm"
            >
              {create.isPending && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
              Add domain
            </button>
          </form>
        ) : (
          <div className="rounded-xl border border-dashed border-border-strong bg-n-50 p-5">
            <h3 className="text-sm font-medium text-foreground">Publish a tool first</h3>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              A custom domain must point to a live deployment, so there is nothing safe to attach
              yet.
            </p>
            <Link to="/dashboard" className="btn btn-secondary mt-4 h-9 text-sm">
              Open your tools
            </Link>
          </div>
        )}
        <ErrorMessage error={create.error} />
      </Panel>

      <Panel title="Connected domains">
        {isLoading ? (
          <Loader2
            className="size-5 animate-spin text-muted-foreground"
            aria-label="Loading domains"
          />
        ) : data?.domains.length ? (
          <ul className="divide-y divide-border">
            {data.domains.map((domain) => (
              <li key={domain.id} className="py-5 first:pt-0 last:pb-0">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <Globe2 className="size-4 text-muted-foreground" aria-hidden="true" />
                      <span className="font-medium text-foreground">{domain.hostname}</span>
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                          domain.status === "verified"
                            ? "bg-success/10 text-success"
                            : domain.status === "error"
                              ? "bg-destructive/10 text-destructive"
                              : "bg-warning/10 text-warning"
                        }`}
                      >
                        {domain.status === "verified" ? "Connected" : domain.status}
                      </span>
                    </div>
                    {domain.status !== "verified" && domain.verification.length > 0 && (
                      <div className="mt-3 overflow-hidden rounded-lg border border-border bg-n-50">
                        {domain.verification.map((record, index) => (
                          <div
                            key={`${record.type}-${record.domain}-${index}`}
                            className="grid gap-1 border-b border-border px-3 py-2.5 text-xs last:border-0 sm:grid-cols-[5rem_1fr]"
                          >
                            <span className="font-mono font-medium text-foreground">
                              {record.type ?? "DNS"}
                            </span>
                            <span className="min-w-0">
                              <span className="block break-all text-muted-foreground">
                                {record.domain}
                              </span>
                              <code className="mt-0.5 block break-all font-mono text-foreground">
                                {record.value}
                              </code>
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                    {domain.last_error && (
                      <p className="mt-2 text-sm text-destructive">{domain.last_error}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {domain.status !== "verified" && (
                      <button
                        type="button"
                        onClick={() => verify.mutate(domain.id)}
                        disabled={verify.isPending}
                        className="btn btn-secondary h-9 text-sm"
                      >
                        <RefreshCw
                          className={`size-4 ${verify.isPending ? "animate-spin" : ""}`}
                          aria-hidden="true"
                        />
                        Verify
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => remove.mutate(domain.id)}
                      disabled={remove.isPending}
                      className="btn btn-ghost h-9 px-3 text-sm text-destructive"
                    >
                      <Trash2 className="size-4" aria-hidden="true" />
                      Remove
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No custom domains are connected.</p>
        )}
        <ErrorMessage error={verify.error || remove.error} />
      </Panel>
    </div>
  );
}

function ApiKeysPanel() {
  const gate = useGate("api_access");
  const { data, isLoading } = useApiKeys();
  const create = useCreateApiKey();
  const revoke = useRevokeApiKey();
  const [name, setName] = useState("");
  const [expiry, setExpiry] = useState("90");
  const [created, setCreated] = useState<CreatedWorkspaceApiKey | null>(null);
  const [copied, setCopied] = useState(false);

  if (gate.loading) return null;
  if (!gate.allowed) return <UpgradeNotice feature="api_access" />;

  return (
    <div className="space-y-5">
      <Panel
        title="Create an API key"
        description="Keys can read this workspace's tools and leads through the developer API. The secret is shown once."
      >
        <form
          className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_12rem_auto] sm:items-end"
          onSubmit={(event) => {
            event.preventDefault();
            create.mutate(
              {
                name: name.trim(),
                expires_in_days: expiry === "never" ? null : Number(expiry),
              },
              {
                onSuccess: (key) => {
                  setCreated(key);
                  setName("");
                  setCopied(false);
                },
              },
            );
          }}
        >
          <Field label="Key name">
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Reporting integration"
              required
              minLength={2}
              className={INPUT}
            />
          </Field>
          <Field label="Expires">
            <select
              value={expiry}
              onChange={(event) => setExpiry(event.target.value)}
              className={SELECT}
            >
              <option value="30">30 days</option>
              <option value="90">90 days</option>
              <option value="365">1 year</option>
              <option value="never">Never</option>
            </select>
          </Field>
          <button
            type="submit"
            disabled={create.isPending || name.trim().length < 2}
            className="btn btn-primary h-11 text-sm"
          >
            {create.isPending && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
            Create key
          </button>
        </form>
        <ErrorMessage error={create.error} />

        {created && (
          <div className="mt-5 rounded-xl border border-warning/35 bg-warning/10 p-4">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-foreground">Copy this key now</p>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                  Magnitai stores only a one-way hash. This secret cannot be shown again.
                </p>
                <code className="mt-3 block overflow-x-auto rounded-lg bg-card p-3 font-mono text-xs text-foreground">
                  {created.key}
                </code>
                <button
                  type="button"
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(created.key);
                      setCopied(true);
                    } catch {
                      setCopied(false);
                    }
                  }}
                  className="btn btn-secondary mt-3 h-9 text-sm"
                >
                  {copied ? (
                    <Check className="size-4" aria-hidden="true" />
                  ) : (
                    <Copy className="size-4" aria-hidden="true" />
                  )}
                  {copied ? "Copied" : "Copy key"}
                </button>
              </div>
            </div>
          </div>
        )}
      </Panel>

      <Panel title="Active keys">
        {isLoading ? (
          <Loader2
            className="size-5 animate-spin text-muted-foreground"
            aria-label="Loading API keys"
          />
        ) : data?.keys.length ? (
          <ul className="divide-y divide-border">
            {data.keys.map((key) => (
              <li
                key={key.id}
                className="flex flex-wrap items-center justify-between gap-4 py-4 first:pt-0 last:pb-0"
              >
                <div>
                  <p className="text-sm font-medium text-foreground">{key.name}</p>
                  <p className="mt-1 font-mono text-xs text-muted-foreground">
                    {key.prefix}••••••••
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {key.last_used_at
                      ? `Last used ${new Date(key.last_used_at).toLocaleString()}`
                      : "Never used"}
                    {" · "}
                    {key.expires_at
                      ? `Expires ${new Date(key.expires_at).toLocaleDateString()}`
                      : "No expiry"}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    revoke.mutate(key.id, {
                      onSuccess: () => {
                        if (created?.id === key.id) setCreated(null);
                      },
                    })
                  }
                  disabled={revoke.isPending}
                  className="btn btn-secondary h-9 text-sm text-destructive"
                >
                  Revoke
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No active API keys.</p>
        )}
        <ErrorMessage error={revoke.error} />
      </Panel>

      <Panel title="Developer endpoints">
        <div className="space-y-2 font-mono text-xs">
          <code className="block rounded-lg bg-n-50 px-3 py-2.5 text-foreground">
            GET /api/developer/tools
          </code>
          <code className="block rounded-lg bg-n-50 px-3 py-2.5 text-foreground">
            GET /api/developer/leads
          </code>
        </div>
        <p className="mt-3 text-xs leading-5 text-muted-foreground">
          Send the key in the <code className="font-mono text-foreground">X-API-Key</code> header.
        </p>
      </Panel>
    </div>
  );
}

function TeamPanel({ invitationToken }: { invitationToken: string | null }) {
  const { data, isLoading } = useTeam();
  const invite = useInviteTeamMember();
  const accept = useAcceptTeamInvitation();
  const remove = useRemoveTeamMember();
  const revoke = useRevokeTeamInvitation();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"admin" | "member">("member");

  return (
    <div className="space-y-5">
      {invitationToken && (
        <Panel className="border-brand-solid/30">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-medium text-foreground">Workspace invitation</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Accept to join the workspace connected to this invitation.
              </p>
            </div>
            <button
              type="button"
              onClick={() => accept.mutate(invitationToken)}
              disabled={accept.isPending}
              className="btn btn-primary h-10 text-sm"
            >
              {accept.isPending && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
              Accept invitation
            </button>
          </div>
          {accept.isSuccess && (
            <p aria-live="polite" className="mt-3 flex items-center gap-2 text-sm text-success">
              <Check className="size-4" aria-hidden="true" />
              Invitation accepted. This workspace is now active.
            </p>
          )}
          <ErrorMessage error={accept.error} />
        </Panel>
      )}

      {data?.can_manage && (
        <Panel
          title="Invite a teammate"
          description="Invitations expire after seven days and can only be accepted by the address you enter."
        >
          <form
            className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_10rem_auto] sm:items-end"
            onSubmit={(event) => {
              event.preventDefault();
              invite.mutate({ email: email.trim(), role }, { onSuccess: () => setEmail("") });
            }}
          >
            <Field label="Email address">
              <input
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="teammate@example.com"
                required
                className={INPUT}
              />
            </Field>
            <Field label="Role">
              <select
                value={role}
                onChange={(event) => setRole(event.target.value as "admin" | "member")}
                className={SELECT}
              >
                <option value="member">Member</option>
                <option value="admin">Admin</option>
              </select>
            </Field>
            <button
              type="submit"
              disabled={invite.isPending || !email.trim()}
              className="btn btn-primary h-11 text-sm"
            >
              {invite.isPending && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
              Send invite
            </button>
          </form>
          <p className="mt-3 text-xs leading-5 text-muted-foreground">
            Admins can change shared settings. Members can work with tools, leads and integrations.
          </p>
          <ErrorMessage error={invite.error} />
        </Panel>
      )}

      <Panel title="Workspace members">
        {isLoading ? (
          <Loader2
            className="size-5 animate-spin text-muted-foreground"
            aria-label="Loading team"
          />
        ) : (
          <ul className="divide-y divide-border">
            {data?.members.map((member) => (
              <li
                key={member.id}
                className="flex flex-wrap items-center justify-between gap-4 py-4 first:pt-0 last:pb-0"
              >
                <div className="flex items-center gap-3">
                  <span className="grid size-9 place-items-center rounded-full bg-secondary text-xs font-semibold text-foreground">
                    {(member.display_name || member.email)[0]?.toUpperCase()}
                  </span>
                  <div>
                    <p className="text-sm font-medium text-foreground">
                      {member.display_name || member.email}
                      {member.is_current_user && (
                        <span className="ml-1.5 font-normal text-muted-foreground">(you)</span>
                      )}
                    </p>
                    {member.display_name && (
                      <p className="mt-0.5 text-xs text-muted-foreground">{member.email}</p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="rounded-full bg-n-100 px-2.5 py-1 text-xs capitalize text-muted-foreground">
                    {member.role}
                  </span>
                  {data?.can_manage && member.role !== "owner" && (
                    <button
                      type="button"
                      onClick={() => remove.mutate(member.id)}
                      disabled={remove.isPending}
                      className="text-xs font-medium text-destructive hover:underline"
                    >
                      Remove
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
        <ErrorMessage error={remove.error} />
      </Panel>

      {data?.can_manage && data.invitations.length > 0 && (
        <Panel title="Pending invitations">
          <ul className="divide-y divide-border">
            {data.invitations.map((pending) => (
              <li
                key={pending.id}
                className="flex flex-wrap items-center justify-between gap-4 py-4 first:pt-0 last:pb-0"
              >
                <div>
                  <p className="text-sm font-medium text-foreground">{pending.email}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {pending.role} · expires {new Date(pending.expires_at).toLocaleDateString()}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => revoke.mutate(pending.id)}
                  disabled={revoke.isPending}
                  className="btn btn-secondary h-9 text-sm"
                >
                  Revoke
                </button>
              </li>
            ))}
          </ul>
          <ErrorMessage error={revoke.error} />
        </Panel>
      )}
    </div>
  );
}

function TwoFactor() {
  const { data: statusData, isLoading } = useMfaStatus();
  const enroll = useEnrollMfa();
  const confirm = useConfirmMfa();
  const disable = useDisableMfa();
  const [code, setCode] = useState("");
  const [codesCopied, setCodesCopied] = useState(false);

  if (isLoading) {
    return (
      <Loader2
        className="size-5 animate-spin text-muted-foreground"
        aria-label="Loading security"
      />
    );
  }

  const recoveryCodes = confirm.data?.recovery_codes;
  if (recoveryCodes) {
    return (
      <div>
        <div className="flex items-start gap-2.5 rounded-xl border border-warning/35 bg-warning/10 p-4">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden="true" />
          <p className="text-sm leading-6 text-foreground">
            Save these recovery codes now. Each works once, and Magnitai stores only their hashes.
          </p>
        </div>
        <ul className="mt-4 grid grid-cols-2 gap-2 rounded-xl bg-n-50 p-4 font-mono text-sm sm:grid-cols-3">
          {recoveryCodes.map((recoveryCode) => (
            <li key={recoveryCode}>{recoveryCode}</li>
          ))}
        </ul>
        <button
          type="button"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(recoveryCodes.join("\n"));
              setCodesCopied(true);
            } catch {
              setCodesCopied(false);
            }
          }}
          className="btn btn-secondary mt-4 h-9 text-sm"
        >
          {codesCopied ? <Check className="size-4" /> : <Copy className="size-4" />}
          {codesCopied ? "Copied" : "Copy codes"}
        </button>
      </div>
    );
  }

  if (statusData?.enabled) {
    return (
      <div>
        <div className="flex items-center gap-2 text-sm font-medium text-foreground">
          <ShieldCheck className="size-4 text-success" aria-hidden="true" />
          Two-factor authentication is on
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          {statusData.recovery_codes_remaining} recovery{" "}
          {statusData.recovery_codes_remaining === 1 ? "code" : "codes"} left.
        </p>
        <form
          className="mt-5 flex flex-wrap items-end gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            disable.mutate(code);
          }}
        >
          <div className="w-48">
            <Field label="Authenticator code">
              <input
                value={code}
                onChange={(event) => setCode(event.target.value)}
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder="123456"
                className={INPUT}
              />
            </Field>
          </div>
          <button
            type="submit"
            disabled={disable.isPending || code.length < 6}
            className="btn btn-secondary h-11 text-sm"
          >
            {disable.isPending && <Loader2 className="size-4 animate-spin" />}
            Disable
          </button>
        </form>
        <ErrorMessage error={disable.error} />
      </div>
    );
  }

  if (enroll.data) {
    return (
      <div>
        <p className="text-sm leading-6 text-muted-foreground">
          Add this secret to your authenticator app, then enter its current six-digit code.
        </p>
        <code className="mt-3 block break-all rounded-lg bg-n-50 p-3 font-mono text-sm text-foreground">
          {enroll.data.secret}
        </code>
        <form
          className="mt-5 flex flex-wrap items-end gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            confirm.mutate(code);
          }}
        >
          <div className="w-48">
            <Field label="Code from the app">
              <input
                value={code}
                onChange={(event) => setCode(event.target.value)}
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder="123456"
                className={INPUT}
              />
            </Field>
          </div>
          <button
            type="submit"
            disabled={confirm.isPending || code.length < 6}
            className="btn btn-primary h-11 text-sm"
          >
            {confirm.isPending && <Loader2 className="size-4 animate-spin" />}
            Turn on
          </button>
        </form>
        <ErrorMessage error={confirm.error} />
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-5">
      <div>
        <p className="text-sm font-medium text-foreground">Two-factor authentication is off</p>
        <p className="mt-1 max-w-xl text-sm leading-6 text-muted-foreground">
          Add a code from your phone after the password step, so a stolen password is not enough.
        </p>
      </div>
      <button
        type="button"
        onClick={() => enroll.mutate()}
        disabled={enroll.isPending}
        className="btn btn-primary h-10 text-sm"
      >
        {enroll.isPending && <Loader2 className="size-4 animate-spin" />}
        Set up 2FA
      </button>
      <ErrorMessage error={enroll.error} />
    </div>
  );
}

function SecurityPanel() {
  return (
    <div className="space-y-5">
      <Panel
        title="Two-factor authentication"
        description="Protect access to the tools and lead data held in this workspace."
      >
        <TwoFactor />
      </Panel>
      <ChangePassword />
    </div>
  );
}

function DataExportPanel() {
  const mutation = useDeleteAccount();
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<Error | null>(null);
  const [password, setPassword] = useState("");
  const [confirmWord, setConfirmWord] = useState("");

  const exportData = async () => {
    setExporting(true);
    setExportError(null);
    try {
      const data = await api.get<Record<string, unknown>>("/api/users/me/export");
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
      );
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `magnitai-workspace-${new Date().toISOString().slice(0, 10)}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setExportError(error as Error);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="space-y-5">
      <Panel
        title="Export workspace data"
        description="Download your account details, tool inventory, activity counts and captured leads as portable JSON."
      >
        <button
          type="button"
          onClick={exportData}
          disabled={exporting}
          className="btn btn-primary h-10 text-sm"
        >
          {exporting ? (
            <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          ) : (
            <Database className="size-4" aria-hidden="true" />
          )}
          Download export
        </button>
        <ErrorMessage error={exportError} />
      </Panel>

      <section className="rounded-[--radius-surface] border border-destructive/35 bg-card p-5 sm:p-6">
        <h2 className="text-base font-medium text-foreground">Delete this account</h2>
        <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
          Permanently removes your account, every tool it owns, and all captured leads. This cannot
          be undone, so export first if you need a record.
        </p>
        <form
          className="mt-5 grid max-w-lg gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            mutation.mutate(password, {
              onSuccess: async () => {
                await logout();
                navigate({ to: "/", replace: true });
              },
            });
          }}
        >
          <Field label="Your password">
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className={INPUT}
            />
          </Field>
          <Field label='Type "delete" to confirm'>
            <input
              value={confirmWord}
              onChange={(event) => setConfirmWord(event.target.value)}
              className={INPUT}
            />
          </Field>
          <button
            type="submit"
            disabled={
              mutation.isPending || !password || confirmWord.trim().toLowerCase() !== "delete"
            }
            className="btn h-10 w-fit bg-destructive text-sm text-white hover:opacity-90"
          >
            {mutation.isPending && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
            Delete my account
          </button>
          <ErrorMessage error={mutation.error} />
        </form>
      </section>
    </div>
  );
}

function LabsPanel() {
  const { user } = useAuth();
  const mutation = useUpdateLabs();
  if (!user) return null;

  return (
    <div className="space-y-5">
      <Panel>
        <div className="flex items-start gap-4">
          <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-brand-wash">
            <FlaskConical className="size-5 text-brand-solid" aria-hidden="true" />
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="text-base font-medium text-foreground">Early access workspace</h2>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
              Opt this workspace into small, reversible product experiments before general release.
              Core publishing, lead delivery and billing behavior never changes through Labs.
            </p>
            <div className="mt-5 border-t border-border pt-5">
              <Toggle
                id="labs-enabled"
                checked={user.labs_enabled}
                disabled={mutation.isPending}
                onChange={(enabled) => mutation.mutate({ enabled })}
                label="Enable Labs"
                hint="New experiments appear here with their own explanation and individual control."
              />
            </div>
            <div aria-live="polite" className="mt-3 min-h-5 text-sm">
              {mutation.isSuccess && (
                <span className="flex items-center gap-2 text-success">
                  <Check className="size-4" aria-hidden="true" />
                  Workspace preference saved
                </span>
              )}
            </div>
            <ErrorMessage error={mutation.error} />
          </div>
        </div>
      </Panel>
      <Panel title="Available experiments">
        <div className="rounded-xl border border-dashed border-border-strong bg-n-50 p-5">
          <p className="text-sm font-medium text-foreground">
            {user.labs_enabled ? "You are ready for the next experiment" : "Labs is currently off"}
          </p>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            There are no active experiments in this release. Nothing experimental is running
            silently in your workspace.
          </p>
        </div>
      </Panel>
    </div>
  );
}

function DetailView({ id, invitationToken }: { id: SettingId; invitationToken: string | null }) {
  const setting = SETTINGS.find((item) => item.id === id)!;
  const panel = {
    profile: <ProfilePanel />,
    workspace: <WorkspacePanel />,
    billing: <BillingPanel />,
    domains: <DomainsPanel />,
    notifications: <NotificationsPanel />,
    "api-keys": <ApiKeysPanel />,
    team: <TeamPanel invitationToken={invitationToken} />,
    security: <SecurityPanel />,
    data: <DataExportPanel />,
    labs: <LabsPanel />,
  } satisfies Record<SettingId, ReactNode>;

  return (
    <div className="mx-auto max-w-4xl">
      <DetailHeader setting={setting} />
      {panel[id]}
    </div>
  );
}

export function SettingsExperience() {
  const href = useRouterState({ select: (state) => state.location.href });
  const hash = useRouterState({ select: (state) => state.location.hash });
  const active = hash.replace(/^#/, "") as SettingId;
  const invitationToken = useMemo(() => {
    const query = href.split("?")[1]?.split("#")[0];
    return query ? new URLSearchParams(query).get("invite") : null;
  }, [href]);
  const valid = SETTINGS.some((setting) => setting.id === active);

  if (valid) {
    return <DetailView id={active} invitationToken={invitationToken} />;
  }

  return (
    <>
      <header className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="font-serif text-[2.25rem] leading-none tracking-[-0.035em] text-foreground">
            Settings
          </h1>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Manage your account, workspace and preferences.
          </p>
        </div>
        <Link to="/dashboard/help" className="btn btn-secondary h-9 w-fit text-sm">
          <LifeBuoy className="size-4" aria-hidden="true" />
          Get help
        </Link>
      </header>
      <SettingsHome />
    </>
  );
}
