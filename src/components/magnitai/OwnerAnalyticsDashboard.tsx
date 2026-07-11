import React from "react";
import { TrendingUp, Users, Zap, Globe, ShieldCheck } from "lucide-react";
import { motion } from "framer-motion";
import { PageShell } from "@/components/magnitai/ui/PageShell";
import { SectionIntro } from "@/components/magnitai/ui/SectionIntro";
import { MetricStat } from "@/components/magnitai/ui/MetricStat";
import { GaugeStat } from "@/components/magnitai/ui/GaugeStat";

export function OwnerAnalyticsDashboard() {
  const metrics = [
    {
      label: "Total Widget Visitors",
      value: "48,290",
      lift: "+14.2%",
      icon: Users,
      color: "text-foreground",
    },
    {
      label: "Interactive Engagements",
      value: "31,402",
      lift: "+28.4%",
      icon: Zap,
      color: "text-primary",
    },
    {
      label: "Lead Webhooks",
      value: "4,912",
      lift: "+8.1%",
      icon: TrendingUp,
      color: "text-foreground",
    },
  ];

  const topWidgets = [
    {
      name: "ROI Calculator",
      location: "Homepage",
      embeds: "strideos.com/",
      conversions: "1,420",
      rate: "18.4%",
      healed: "Just now",
    },
    {
      name: "Pricing Tier Matcher",
      location: "Pricing",
      embeds: "strideos.com/pricing",
      conversions: "2,190",
      rate: "34.1%",
      healed: "3 days ago",
    },
    {
      name: "Free SEO Auditor",
      location: "Blog",
      embeds: "blog.strideos.com/tools",
      conversions: "812",
      rate: "12.0%",
      healed: "12 days ago",
    },
  ];

  return (
    <PageShell>
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-20">
        <SectionIntro
          dot="success"
          eyebrow="Telemetry live"
          heading={<>Analytics &amp; <span className="hero-accent">self-healing</span></>}
          className="w-full"
        />
        <div className="flex items-center gap-4 pb-2">
          <span className="text-[11px] text-muted-foreground font-mono font-bold tracking-widest uppercase">
            Updated 2s ago
          </span>
          <button className="h-10 px-6 rounded-full bg-card border border-border text-foreground font-bold text-sm hover:bg-secondary active:scale-95 transition-all">
            Export CSV
          </button>
        </div>
      </div>

      {/* Top Cards - Denoised, no borders */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-10 mb-24">
        {metrics.map((m, idx) => (
          <MetricStat
            key={idx}
            icon={m.icon}
            iconColor={m.color}
            subLabel={m.label}
            value={m.value}
            label={m.label}
            badge={m.lift}
            valueSize="lg"
          />
        ))}
        <GaugeStat value={100} displayValue="100%" label="DOM repairs auto-healed" color="text-success" />
      </div>

      {/* Table Section - Airy layout */}
      <div>
        <div className="flex justify-between items-end mb-8">
          <h3 className="font-heading font-semibold text-foreground text-2xl tracking-tight">
            Active Containers
          </h3>
          <span className="eyebrow">3 live</span>
        </div>

        <div className="overflow-x-auto [mask-image:linear-gradient(to_right,black_calc(100%-2rem),transparent)] sm:[mask-image:none]">
          <table className="w-full min-w-[640px] text-left border-collapse sm:min-w-0">
            <thead>
              <tr className="border-b border-border text-[11px] uppercase tracking-widest text-muted-foreground font-bold">
                <th className="pb-4 pr-6">Widget Container</th>
                <th className="pb-4 px-6">Host Location</th>
                <th className="pb-4 px-6 text-right">Leads</th>
                <th className="pb-4 px-6 text-right">Conv. Lift</th>
                <th className="pb-4 pl-6 text-right">Sentinel Status</th>
              </tr>
            </thead>
            <motion.tbody
              initial="hidden"
              animate="visible"
              variants={{ visible: { transition: { staggerChildren: 0.1 } } }}
              className="font-medium"
            >
              {topWidgets.map((row, idx) => (
                <motion.tr
                  variants={{
                    hidden: { opacity: 0, y: 20 },
                    visible: { opacity: 1, y: 0, transition: { duration: 0.5 } },
                  }}
                  key={idx}
                  className="hover:bg-secondary/50 transition-colors group"
                >
                  <td className="py-4 md:py-8 pr-6 rounded-l-2xl">
                    <div className="font-bold text-foreground text-base group-hover:text-primary transition-colors pl-4">
                      {row.name}
                    </div>
                  </td>
                  <td className="py-4 md:py-8 px-6">
                    <div className="font-bold text-foreground mb-1">{row.location}</div>
                    <div className="font-mono text-xs text-muted-foreground flex items-center gap-1.5">
                      <Globe className="size-3.5" /> {row.embeds}
                    </div>
                  </td>
                  <td className="py-4 md:py-8 px-6 font-mono font-bold text-foreground text-right text-lg">
                    {row.conversions}
                  </td>
                  <td className="py-4 md:py-8 px-6 font-mono font-bold text-success text-right text-lg">
                    {row.rate}
                  </td>
                  <td className="py-4 md:py-8 pl-6 text-right rounded-r-2xl pr-4">
                    <span className="inline-flex items-center gap-1.5 bg-success/10 text-success font-bold text-[11px] uppercase tracking-widest px-3 py-1.5 rounded-full">
                      <ShieldCheck className="size-3.5" /> {row.healed}
                    </span>
                  </td>
                </motion.tr>
              ))}
            </motion.tbody>
          </table>
        </div>
      </div>
    </PageShell>
  );
}
