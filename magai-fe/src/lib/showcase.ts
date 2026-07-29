import type { ArchitectOutput } from "./api";

/**
 * Playable examples for the gallery, in the exact shape the builder produces.
 *
 * Typed as `ArchitectOutput` on purpose: these render through the same
 * `DecisionPreview` and the same scoring the real pipeline emits, so a visitor
 * who plays one has genuinely used the product. A screenshot would be cheaper
 * and would prove nothing — a live demo is reported to draw interaction from
 * around 89% of visitors against roughly 6% for a conventional landing page,
 * and the whole problem with the old gallery was that it described five formats
 * without letting anyone touch one.
 *
 * The businesses are deliberately generic — "a dental practice", not a named
 * company. Dressing an example in a real brand implies a customer relationship
 * that does not exist, and this product's entire discipline is not claiming
 * things it cannot evidence.
 */

const CALM_VISUAL = {
  layout: "centered-single-column",
  spacing: "comfortable",
  card_style: "solid-white",
  border_radius: "rounded",
  shadow_depth: "subtle",
  button_style: "filled-solid",
  decorative_elements: "none",
  icon_style: "outlined",
  visual_energy: "calm",
};

export interface ShowcaseExample {
  id: string;
  business: string;
  sector: string;
  /** Why this format suits this business — the judgement the analyzer makes. */
  reasoning: string;
  architect: ArchitectOutput;
}

export const SHOWCASE: ShowcaseExample[] = [
  {
    id: "dental-recovered-bookings",
    business: "A dental practice",
    sector: "Local service",
    reasoning:
      "The value of a clearer booking path is easier to calculate than to argue, so the tool does the arithmetic in front of them.",
    architect: {
      widget_type: "roi_calculator",
      brand: {
        primary_color: "#17324d",
        secondary_color: "#4a5a6a",
        background_color: "#ffffff",
        accent_color: "#e8b05c",
        font_headings: "system-ui",
        font_body: "system-ui",
        tone: "calm-professional",
        logo_url: null,
      },
      visual_language: CALM_VISUAL,
      logic: {
        formula: "New patients a month, weighted by how much of the booking path is measured.",
        variables: [
          { name: "monthly_patients", description: "new patients a month", default: "25" },
        ],
        example_calculation: "25 new patients, 8% recovered, is two more a month.",
      },
      copywriting: {
        headline: "What is a clearer booking path worth?",
        subheadline: "Four questions, then an estimate you can act on.",
        cta: "See my estimate",
      },
      claims: [],
      decision: {
        mechanism: "estimate",
        buyer_question: "What is a clearer booking path worth to this practice?",
        value_before_gate: "A monthly recovered-bookings estimate with its assumptions shown",
        qualification_goal: "Practice size and how much of the journey is currently measured",
        recommended_placement: "New patients page",
        questions: [
          {
            id: "monthly_patients",
            label: "New patients a month",
            help_text: "Your current average is fine.",
            input_type: "number",
            required: true,
            options: [],
            minimum: 0,
            maximum: 200,
            step: 1,
            default: 25,
            weight: 2,
            option_scores: [],
            true_score: 100,
            evidence_ref: null,
          },
          {
            id: "booking_path",
            label: "How does someone book today?",
            help_text: "",
            input_type: "single_choice",
            required: true,
            options: ["Phone only", "A form we reply to", "Real-time online booking"],
            minimum: null,
            maximum: null,
            step: null,
            default: null,
            weight: 3,
            option_scores: [90, 55, 20],
            true_score: 100,
            evidence_ref: null,
          },
          {
            id: "tracks_enquiries",
            label: "Do you track where enquiries come from?",
            help_text: "",
            input_type: "boolean",
            required: true,
            options: [],
            minimum: null,
            maximum: null,
            step: null,
            default: null,
            weight: 2,
            option_scores: [],
            true_score: 15,
            evidence_ref: null,
          },
        ],
        results: [
          {
            key: "steady",
            title: "Your booking path is broadly working",
            summary: "Most people who want an appointment are getting one without much friction.",
            recommendation:
              "Keep an eye on response time — that is usually the first thing to slip.",
            minimum_score: 0,
            maximum_score: 44,
          },
          {
            key: "recoverable",
            title: "There is real revenue in a clearer path",
            summary:
              "Enough enquiries are stalling between interest and appointment to be worth fixing.",
            recommendation:
              "Start with online booking on the new-patient page, then measure what changes.",
            minimum_score: 45,
            maximum_score: 100,
          },
        ],
        calculation: {
          kind: "weighted_score",
          output_label: "Recoverable opportunity",
          output_format: "score",
          currency: "USD",
          decimals: 0,
          constant: 0,
          terms: [],
          clamp_min: 0,
          clamp_max: 100,
        },
        qualification_threshold: 45,
        lead_gate: "after_value",
        primary_cta: "Discuss this estimate",
        evidence_refs: [],
      },
    } as ArchitectOutput,
  },
  {
    id: "solar-readiness",
    business: "A solar installer",
    sector: "Home improvement",
    reasoning:
      "A long, expensive decision where the buyer needs to see their own situation before they will talk to anyone.",
    architect: {
      widget_type: "readiness_quiz",
      brand: {
        primary_color: "#0b3d2c",
        secondary_color: "#44584f",
        background_color: "#ffffff",
        accent_color: "#f2a71b",
        font_headings: "system-ui",
        font_body: "system-ui",
        tone: "direct-practical",
        logo_url: null,
      },
      visual_language: CALM_VISUAL,
      logic: {
        formula: "Roof suitability, usage and ownership, weighted toward the blocking factors.",
        variables: [{ name: "roof_aspect", description: "roof direction", default: "South" }],
        example_calculation: "A south-facing roof on an owned home scores highest.",
      },
      copywriting: {
        headline: "Is your roof worth quoting?",
        subheadline: "Three questions and an honest answer, including no.",
        cta: "Check my roof",
      },
      claims: [],
      decision: {
        mechanism: "diagnose",
        buyer_question: "Would solar actually pay back on this particular house?",
        value_before_gate: "A straight yes, not yet, or no — with the reason",
        qualification_goal: "Whether this is a quotable property at all",
        recommended_placement: "Homepage hero",
        questions: [
          {
            id: "ownership",
            label: "Do you own the property?",
            help_text: "",
            input_type: "boolean",
            required: true,
            options: [],
            minimum: null,
            maximum: null,
            step: null,
            default: null,
            weight: 3,
            option_scores: [],
            true_score: 100,
            evidence_ref: null,
          },
          {
            id: "roof_aspect",
            label: "Which way does most of your roof face?",
            help_text: "A rough answer is fine.",
            input_type: "single_choice",
            required: true,
            options: ["South", "East or west", "North", "I'm not sure"],
            minimum: null,
            maximum: null,
            step: null,
            default: null,
            weight: 3,
            option_scores: [100, 65, 20, 50],
            true_score: 100,
            evidence_ref: null,
          },
          {
            id: "monthly_bill",
            label: "Roughly what is your monthly electricity bill?",
            help_text: "",
            input_type: "number",
            required: true,
            options: [],
            minimum: 0,
            maximum: 600,
            step: 10,
            default: 120,
            weight: 2,
            option_scores: [],
            true_score: 100,
            evidence_ref: null,
          },
        ],
        results: [
          {
            key: "not_yet",
            title: "Solar is unlikely to pay back here",
            summary:
              "On this combination of roof and usage the numbers do not work well enough to recommend it.",
            recommendation:
              "Worth revisiting if your usage rises or you change the roof. We will not push a quote.",
            minimum_score: 0,
            maximum_score: 39,
          },
          {
            key: "worth_quoting",
            title: "This is worth a proper quote",
            summary: "Your roof and usage are in the range where solar typically pays back.",
            recommendation: "A site survey is the next step — it takes about twenty minutes.",
            minimum_score: 40,
            maximum_score: 100,
          },
        ],
        calculation: {
          kind: "weighted_score",
          output_label: "Suitability",
          output_format: "score",
          currency: "USD",
          decimals: 0,
          constant: 0,
          terms: [],
          clamp_min: 0,
          clamp_max: 100,
        },
        qualification_threshold: 40,
        lead_gate: "after_value",
        primary_cta: "Book a survey",
        evidence_refs: [],
      },
    } as ArchitectOutput,
  },
  {
    id: "saas-onboarding-audit",
    business: "A B2B software company",
    sector: "SaaS",
    reasoning:
      "The buyer already suspects something is wrong but cannot name it, so the tool grades it for them.",
    architect: {
      widget_type: "audit_tool",
      brand: {
        primary_color: "#1a1a2e",
        secondary_color: "#4b4b63",
        background_color: "#ffffff",
        accent_color: "#5b6cff",
        font_headings: "system-ui",
        font_body: "system-ui",
        tone: "precise-technical",
        logo_url: null,
      },
      visual_language: CALM_VISUAL,
      logic: {
        formula: "Activation, time-to-value and instrumentation, weighted toward measurement.",
        variables: [{ name: "time_to_value", description: "days to first value", default: "7" }],
        example_calculation: "Under a day to first value scores highest.",
      },
      copywriting: {
        headline: "Where is your onboarding losing people?",
        subheadline: "Four questions, then the one thing to fix first.",
        cta: "Grade my onboarding",
      },
      claims: [],
      decision: {
        mechanism: "diagnose",
        buyer_question: "Which part of onboarding is costing us the most activations?",
        value_before_gate: "A graded breakdown and the single highest-leverage fix",
        qualification_goal: "Team size and whether activation is measured at all",
        recommended_placement: "Product tour page",
        questions: [
          {
            id: "time_to_value",
            label: "How long until a new user gets something useful?",
            help_text: "In days. Best guess is fine.",
            input_type: "number",
            required: true,
            options: [],
            minimum: 0,
            maximum: 30,
            step: 1,
            default: 3,
            weight: 3,
            option_scores: [],
            true_score: 100,
            evidence_ref: null,
          },
          {
            id: "measures_activation",
            label: "Do you have an activation metric you agree on?",
            help_text: "",
            input_type: "boolean",
            required: true,
            options: [],
            minimum: null,
            maximum: null,
            step: null,
            default: null,
            weight: 3,
            option_scores: [],
            true_score: 20,
            evidence_ref: null,
          },
          {
            id: "first_run",
            label: "What does a brand-new account see first?",
            help_text: "",
            input_type: "single_choice",
            required: true,
            options: [
              "An empty dashboard",
              "A checklist or tour",
              "Sample data they can play with",
            ],
            minimum: null,
            maximum: null,
            step: null,
            default: null,
            weight: 3,
            option_scores: [95, 55, 20],
            true_score: 100,
            evidence_ref: null,
          },
        ],
        results: [
          {
            key: "healthy",
            title: "Onboarding is not your bottleneck",
            summary: "New accounts reach something useful quickly and you can see it happening.",
            recommendation: "Look further down the funnel — expansion is the likelier constraint.",
            minimum_score: 0,
            maximum_score: 49,
          },
          {
            key: "leaking",
            title: "You are losing people before first value",
            summary:
              "The gap between signing up and getting something useful is where the activations are going.",
            recommendation:
              "Put real sample data in the empty state, then measure the change against one agreed metric.",
            minimum_score: 50,
            maximum_score: 100,
          },
        ],
        calculation: {
          kind: "weighted_score",
          output_label: "Onboarding risk",
          output_format: "score",
          currency: "USD",
          decimals: 0,
          constant: 0,
          terms: [],
          clamp_min: 0,
          clamp_max: 100,
        },
        qualification_threshold: 50,
        lead_gate: "after_value",
        primary_cta: "Talk through the fix",
        evidence_refs: [],
      },
    } as ArchitectOutput,
  },
];
