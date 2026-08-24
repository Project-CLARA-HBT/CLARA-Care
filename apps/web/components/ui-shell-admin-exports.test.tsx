import { describe, expect, it } from "vitest";

// Test components/ui index exports
import * as UIIndex from "@/components/ui";

// Test individual UI components
import * as ActionObjectMod from "@/components/ui/action-object";
import ActionObjectDefault, { ActionObject } from "@/components/ui/action-object";
import * as AlertMod from "@/components/ui/alert";
import AlertDefault, { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import * as AsyncSectionMod from "@/components/ui/async-section";
import AsyncSectionDefault, { AsyncSection } from "@/components/ui/async-section";
import * as BadgeMod from "@/components/ui/badge";
import BadgeDefault, { Badge } from "@/components/ui/badge";
import * as ButtonMod from "@/components/ui/button";
import ButtonDefault, { Button } from "@/components/ui/button";
import * as CitationAnchorMod from "@/components/ui/citation-anchor";
import CitationAnchorDefault, { CitationAnchor } from "@/components/ui/citation-anchor";
import * as DataRowMod from "@/components/ui/data-row";
import DataRowDefault, { DataRow } from "@/components/ui/data-row";
import * as DataTableMod from "@/components/ui/data-table";
import DataTableDefault, { DataTable } from "@/components/ui/data-table";
import * as EditorialSectionMod from "@/components/ui/editorial-section";
import EditorialSectionDefault, { EditorialSection } from "@/components/ui/editorial-section";
import * as EmptyStateMod from "@/components/ui/empty-state";
import EmptyStateDefault, { EmptyState } from "@/components/ui/empty-state";
import * as FieldMod from "@/components/ui/field";
import FieldDefault, { Field, Select, Textarea } from "@/components/ui/field";
import * as HeroObjectMod from "@/components/ui/hero-object";
import HeroObjectDefault, { HeroObject } from "@/components/ui/hero-object";
import * as IconMod from "@/components/ui/icon";
import IconDefault, { Icon } from "@/components/ui/icon";
import * as InspectorMod from "@/components/ui/inspector";
import InspectorDefault, { Inspector, InspectorField, InspectorSection } from "@/components/ui/inspector";
import * as ListRowMod from "@/components/ui/list-row";
import ListRowDefault, { ListRow } from "@/components/ui/list-row";
import * as LocalRailMod from "@/components/ui/local-rail";
import LocalRailDefault, { LocalRail } from "@/components/ui/local-rail";
import * as MedicalTermMod from "@/components/ui/medical-term";
import MedicalTermDefault, { MedicalTerm } from "@/components/ui/medical-term";
import * as ModalMod from "@/components/ui/modal";
import ModalDefault, { Modal } from "@/components/ui/modal";
import * as PageShellMod from "@/components/ui/page-shell";
import PageShellDefault, { PageShell } from "@/components/ui/page-shell";
import * as SectionIndexMod from "@/components/ui/section-index";
import SectionIndexDefault, { SectionIndex } from "@/components/ui/section-index";
import * as SegmentedControlMod from "@/components/ui/segmented-control";
import SegmentedControlDefault, { SegmentedControl } from "@/components/ui/segmented-control";
import * as SheetMod from "@/components/ui/sheet";
import SheetDefault, {
  Sheet,
  SheetBody,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  useSheetContext,
} from "@/components/ui/sheet";
import * as SourceDisclosureMod from "@/components/ui/source-disclosure";
import SourceDisclosureDefault, {
  SourceDisclosure,
  SourceDisclosureBadge,
  SourceDisclosurePanel,
  SourceItemCard,
} from "@/components/ui/source-disclosure";
import * as StatusChipMod from "@/components/ui/status-chip";
import StatusChipDefault, { StatusChip } from "@/components/ui/status-chip";
import * as StepperMod from "@/components/ui/stepper";
import StepperDefault, { Stepper } from "@/components/ui/stepper";
import * as SurfaceMod from "@/components/ui/surface";
import SurfaceDefault, {
  EmptyState as SurfaceEmptyState,
  InlineError,
  LoadingCards,
  StatCard,
  SurfaceCard,
} from "@/components/ui/surface";
import * as TabsMod from "@/components/ui/tabs";
import TabsDefault, { TabPanel, Tabs } from "@/components/ui/tabs";
import * as TimelineMod from "@/components/ui/timeline";
import TimelineDefault, {
  Timeline,
  TimelineConnector,
  TimelineContent,
  TimelineDescription,
  TimelineItem,
  TimelineNode,
  TimelineTimestamp,
  TimelineTitle,
  useTimelineContext,
} from "@/components/ui/timeline";
import * as ToggleMod from "@/components/ui/toggle";
import ToggleDefault, { Toggle } from "@/components/ui/toggle";

// Test components/shell exports
import * as ShellIndex from "@/components/shell";
import * as PreviewContextStripMod from "@/components/shell/preview-context-strip";
import PreviewContextStripDefault, { PreviewContextStrip } from "@/components/shell/preview-context-strip";
import * as AdminPreviewBannerMod from "@/components/shell/admin-preview-banner";
import AdminPreviewBannerDefault, { AdminPreviewBanner } from "@/components/shell/admin-preview-banner";
import * as ChromeSurfaceMod from "@/components/shell/chrome-surface";
import ChromeSurfaceDefault, { ChromeSurface, Surface as ShellSurface } from "@/components/shell/chrome-surface";
import * as ClaraOrbMod from "@/components/shell/clara-orb";
import ClaraOrbDefault, { ClaraOrb } from "@/components/shell/clara-orb";
import * as CommandPaletteMod from "@/components/shell/command-palette";
import CommandPaletteDefault, { CommandPalette } from "@/components/shell/command-palette";
import * as CommandPaletteProviderMod from "@/components/shell/command-palette-provider";
import CommandPaletteProviderDefault, {
  CommandPaletteProvider,
  useCommandPaletteContext,
} from "@/components/shell/command-palette-provider";
import * as ConsumerLayoutMod from "@/components/shell/consumer-layout";
import ConsumerLayoutDefault, { ConsumerLayout } from "@/components/shell/consumer-layout";
import * as WorkspaceDockMod from "@/components/shell/workspace-dock";
import WorkspaceDockDefault, { WorkspaceDock } from "@/components/shell/workspace-dock";
import * as FloatingPrimaryDockMod from "@/components/shell/floating-primary-dock";
import FloatingPrimaryDockDefault, { FloatingPrimaryDock } from "@/components/shell/floating-primary-dock";
import * as GlobalContextBarMod from "@/components/shell/global-context-bar";
import GlobalContextBarDefault, { GlobalContextBar } from "@/components/shell/global-context-bar";
import * as PreferenceProviderMod from "@/components/shell/preference-provider";
import PreferenceProviderDefault, {
  PreferenceProvider,
  usePreferences,
} from "@/components/shell/preference-provider";
import * as ProfessionalLayoutMod from "@/components/shell/professional-layout";
import ProfessionalLayoutDefault, { ProfessionalLayout } from "@/components/shell/professional-layout";
import * as ProfileBoundaryMod from "@/components/shell/profile-boundary";
import ProfileBoundaryDefault, {
  ProfileBoundary,
  useProfileBoundary,
  useProfileContext,
} from "@/components/shell/profile-boundary";
import * as SessionBoundaryMod from "@/components/shell/session-boundary";
import SessionBoundaryDefault, { SessionBoundary, useSession } from "@/components/shell/session-boundary";
import * as ShellModeProviderMod from "@/components/shell/shell-mode-provider";
import ShellModeProviderDefault, {
  ShellModeProvider,
  useShellMode,
} from "@/components/shell/shell-mode-provider";

// Test components/admin exports
import * as AdminIndex from "@/components/admin";
import * as AdminShellMod from "@/components/admin/admin-shell";
import AdminShellDefault, { AdminShell } from "@/components/admin/admin-shell";
import * as AdminCommandStripMod from "@/components/admin/admin-command-strip";
import AdminCommandStripDefault, { AdminCommandStrip } from "@/components/admin/admin-command-strip";
import * as AdminAppLauncherModalMod from "@/components/admin/admin-app-launcher-modal";
import AdminAppLauncherModalDefault, { AdminAppLauncherModal } from "@/components/admin/admin-app-launcher-modal";
import * as AdminOverviewPanelMod from "@/components/admin/admin-overview-panel";
import AdminOverviewPanelDefault, { AdminOverviewPanel } from "@/components/admin/admin-overview-panel";
import * as AdminObservabilityPanelMod from "@/components/admin/admin-observability-panel";
import AdminObservabilityPanelDefault, { AdminObservabilityPanel } from "@/components/admin/admin-observability-panel";
import * as AdminAnswerFlowPanelMod from "@/components/admin/admin-answer-flow-panel";
import AdminAnswerFlowPanelDefault, { AdminAnswerFlowPanel } from "@/components/admin/admin-answer-flow-panel";
import * as AdminFlowDebuggerMod from "@/components/admin/admin-flow-debugger";
import AdminFlowDebuggerDefault, { AdminFlowDebugger } from "@/components/admin/admin-flow-debugger";
import * as AdminFlowRuntimePanelMod from "@/components/admin/admin-flow-runtime-panel";
import AdminFlowRuntimePanelDefault, { AdminFlowRuntimePanel } from "@/components/admin/admin-flow-runtime-panel";
import * as AdminFlowVisualizerMod from "@/components/admin/admin-flow-visualizer";
import AdminFlowVisualizerDefault, { AdminFlowVisualizer } from "@/components/admin/admin-flow-visualizer";
import * as AdminNeuralNetworkVisualizerMod from "@/components/admin/admin-neural-network-visualizer";
import AdminNeuralNetworkVisualizerDefault, {
  AdminNeuralNetworkVisualizer,
} from "@/components/admin/admin-neural-network-visualizer";
import * as AdminAuditPanelMod from "@/components/admin/admin-audit-panel";
import AdminAuditPanelDefault, { AdminAuditPanel } from "@/components/admin/admin-audit-panel";
import * as AdminRagSourcesPanelMod from "@/components/admin/admin-rag-sources-panel";
import AdminRagSourcesPanelDefault, { AdminRagSourcesPanel } from "@/components/admin/admin-rag-sources-panel";
import * as ProductAnalyticsPanelMod from "@/components/admin/product-analytics-panel";
import ProductAnalyticsPanelDefault, { ProductAnalyticsPanel } from "@/components/admin/product-analytics-panel";
import * as ClinicalAnalyticsPanelMod from "@/components/admin/clinical-analytics-panel";
import ClinicalAnalyticsPanelDefault, { ClinicalAnalyticsPanel } from "@/components/admin/clinical-analytics-panel";
import * as AnalyticsDateRangeMod from "@/components/admin/analytics-date-range";
import AnalyticsDateRangeDefault, { AnalyticsDateRange } from "@/components/admin/analytics-date-range";
import { BarList, KpiCard, PanelCard, TrendBars } from "@/components/admin/analytics-primitives";
import useControlTowerConfigDefault, { useControlTowerConfig } from "@/components/admin/use-control-tower-config";

describe("UI, Shell, and Admin Component Exports Audit (React Error #130 Guard)", () => {
  describe("components/ui modules (named and default exports)", () => {
    it("exports ActionObject", () => {
      expect(ActionObject).toBeDefined();
      expect(ActionObjectDefault).toBeDefined();
      expect(ActionObjectMod.ActionObject).toBeDefined();
      expect(ActionObjectMod.default).toBeDefined();
    });

    it("exports Alert", () => {
      expect(Alert).toBeDefined();
      expect(AlertDefault).toBeDefined();
      expect(AlertTitle).toBeDefined();
      expect(AlertDescription).toBeDefined();
      expect(AlertMod.Alert).toBeDefined();
      expect(AlertMod.default).toBeDefined();
    });

    it("exports AsyncSection", () => {
      expect(AsyncSection).toBeDefined();
      expect(AsyncSectionDefault).toBeDefined();
      expect(AsyncSectionMod.AsyncSection).toBeDefined();
      expect(AsyncSectionMod.default).toBeDefined();
    });

    it("exports Badge", () => {
      expect(Badge).toBeDefined();
      expect(BadgeDefault).toBeDefined();
      expect(BadgeMod.Badge).toBeDefined();
      expect(BadgeMod.default).toBeDefined();
    });

    it("exports Button", () => {
      expect(Button).toBeDefined();
      expect(ButtonDefault).toBeDefined();
      expect(ButtonMod.Button).toBeDefined();
      expect(ButtonMod.default).toBeDefined();
    });

    it("exports CitationAnchor", () => {
      expect(CitationAnchor).toBeDefined();
      expect(CitationAnchorDefault).toBeDefined();
      expect(CitationAnchorMod.CitationAnchor).toBeDefined();
      expect(CitationAnchorMod.default).toBeDefined();
    });

    it("exports DataRow", () => {
      expect(DataRow).toBeDefined();
      expect(DataRowDefault).toBeDefined();
      expect(DataRowMod.DataRow).toBeDefined();
      expect(DataRowMod.default).toBeDefined();
    });

    it("exports DataTable", () => {
      expect(DataTable).toBeDefined();
      expect(DataTableDefault).toBeDefined();
      expect(DataTableMod.DataTable).toBeDefined();
      expect(DataTableMod.default).toBeDefined();
    });

    it("exports EditorialSection", () => {
      expect(EditorialSection).toBeDefined();
      expect(EditorialSectionDefault).toBeDefined();
      expect(EditorialSectionMod.EditorialSection).toBeDefined();
      expect(EditorialSectionMod.default).toBeDefined();
    });

    it("exports EmptyState", () => {
      expect(EmptyState).toBeDefined();
      expect(EmptyStateDefault).toBeDefined();
      expect(EmptyStateMod.EmptyState).toBeDefined();
      expect(EmptyStateMod.default).toBeDefined();
    });

    it("exports Field, Textarea, Select", () => {
      expect(Field).toBeDefined();
      expect(FieldDefault).toBeDefined();
      expect(Textarea).toBeDefined();
      expect(Select).toBeDefined();
      expect(FieldMod.Field).toBeDefined();
      expect(FieldMod.default).toBeDefined();
    });

    it("exports HeroObject", () => {
      expect(HeroObject).toBeDefined();
      expect(HeroObjectDefault).toBeDefined();
      expect(HeroObjectMod.HeroObject).toBeDefined();
      expect(HeroObjectMod.default).toBeDefined();
    });

    it("exports Icon", () => {
      expect(Icon).toBeDefined();
      expect(IconDefault).toBeDefined();
      expect(IconMod.Icon).toBeDefined();
      expect(IconMod.default).toBeDefined();
    });

    it("exports Inspector", () => {
      expect(Inspector).toBeDefined();
      expect(InspectorDefault).toBeDefined();
      expect(InspectorField).toBeDefined();
      expect(InspectorSection).toBeDefined();
      expect(InspectorMod.Inspector).toBeDefined();
      expect(InspectorMod.default).toBeDefined();
    });

    it("exports ListRow", () => {
      expect(ListRow).toBeDefined();
      expect(ListRowDefault).toBeDefined();
      expect(ListRowMod.ListRow).toBeDefined();
      expect(ListRowMod.default).toBeDefined();
    });

    it("exports LocalRail", () => {
      expect(LocalRail).toBeDefined();
      expect(LocalRailDefault).toBeDefined();
      expect(LocalRailMod.LocalRail).toBeDefined();
      expect(LocalRailMod.default).toBeDefined();
    });

    it("exports MedicalTerm", () => {
      expect(MedicalTerm).toBeDefined();
      expect(MedicalTermDefault).toBeDefined();
      expect(MedicalTermMod.MedicalTerm).toBeDefined();
      expect(MedicalTermMod.default).toBeDefined();
    });

    it("exports Modal", () => {
      expect(Modal).toBeDefined();
      expect(ModalDefault).toBeDefined();
      expect(ModalMod.Modal).toBeDefined();
      expect(ModalMod.default).toBeDefined();
    });

    it("exports PageShell", () => {
      expect(PageShell).toBeDefined();
      expect(PageShellDefault).toBeDefined();
      expect(PageShellMod.PageShell).toBeDefined();
      expect(PageShellMod.default).toBeDefined();
    });

    it("exports SectionIndex", () => {
      expect(SectionIndex).toBeDefined();
      expect(SectionIndexDefault).toBeDefined();
      expect(SectionIndexMod.SectionIndex).toBeDefined();
      expect(SectionIndexMod.default).toBeDefined();
    });

    it("exports SegmentedControl", () => {
      expect(SegmentedControl).toBeDefined();
      expect(SegmentedControlDefault).toBeDefined();
      expect(SegmentedControlMod.SegmentedControl).toBeDefined();
      expect(SegmentedControlMod.default).toBeDefined();
    });

    it("exports Sheet and subcomponents", () => {
      expect(Sheet).toBeDefined();
      expect(SheetDefault).toBeDefined();
      expect(SheetHeader).toBeDefined();
      expect(SheetTitle).toBeDefined();
      expect(SheetDescription).toBeDefined();
      expect(SheetBody).toBeDefined();
      expect(SheetFooter).toBeDefined();
      expect(useSheetContext).toBeDefined();
      expect(SheetMod.Sheet).toBeDefined();
      expect(SheetMod.default).toBeDefined();
    });

    it("exports SourceDisclosure and subcomponents", () => {
      expect(SourceDisclosure).toBeDefined();
      expect(SourceDisclosureDefault).toBeDefined();
      expect(SourceDisclosureBadge).toBeDefined();
      expect(SourceDisclosurePanel).toBeDefined();
      expect(SourceItemCard).toBeDefined();
      expect(SourceDisclosureMod.SourceDisclosure).toBeDefined();
      expect(SourceDisclosureMod.default).toBeDefined();
    });

    it("exports StatusChip", () => {
      expect(StatusChip).toBeDefined();
      expect(StatusChipDefault).toBeDefined();
      expect(StatusChipMod.StatusChip).toBeDefined();
      expect(StatusChipMod.default).toBeDefined();
    });

    it("exports Stepper", () => {
      expect(Stepper).toBeDefined();
      expect(StepperDefault).toBeDefined();
      expect(StepperMod.Stepper).toBeDefined();
      expect(StepperMod.default).toBeDefined();
    });

    it("exports Surface primitives", () => {
      expect(SurfaceCard).toBeDefined();
      expect(SurfaceDefault).toBeDefined();
      expect(StatCard).toBeDefined();
      expect(InlineError).toBeDefined();
      expect(LoadingCards).toBeDefined();
      expect(SurfaceEmptyState).toBeDefined();
      expect(SurfaceMod.SurfaceCard).toBeDefined();
      expect(SurfaceMod.default).toBeDefined();
    });

    it("exports Tabs", () => {
      expect(Tabs).toBeDefined();
      expect(TabsDefault).toBeDefined();
      expect(TabPanel).toBeDefined();
      expect(TabsMod.Tabs).toBeDefined();
      expect(TabsMod.default).toBeDefined();
    });

    it("exports Timeline and subcomponents", () => {
      expect(Timeline).toBeDefined();
      expect(TimelineDefault).toBeDefined();
      expect(TimelineNode).toBeDefined();
      expect(TimelineConnector).toBeDefined();
      expect(TimelineTitle).toBeDefined();
      expect(TimelineDescription).toBeDefined();
      expect(TimelineTimestamp).toBeDefined();
      expect(TimelineContent).toBeDefined();
      expect(TimelineItem).toBeDefined();
      expect(useTimelineContext).toBeDefined();
      expect(TimelineMod.Timeline).toBeDefined();
      expect(TimelineMod.default).toBeDefined();
    });

    it("exports Toggle", () => {
      expect(Toggle).toBeDefined();
      expect(ToggleDefault).toBeDefined();
      expect(ToggleMod.Toggle).toBeDefined();
      expect(ToggleMod.default).toBeDefined();
    });

    it("barrel index.ts exports all 29 UI primitives without undefined", () => {
      expect(UIIndex.ActionObject).toBeDefined();
      expect(UIIndex.Alert).toBeDefined();
      expect(UIIndex.AsyncSection).toBeDefined();
      expect(UIIndex.Badge).toBeDefined();
      expect(UIIndex.Button).toBeDefined();
      expect(UIIndex.CitationAnchor).toBeDefined();
      expect(UIIndex.DataRow).toBeDefined();
      expect(UIIndex.DataTable).toBeDefined();
      expect(UIIndex.EditorialSection).toBeDefined();
      expect(UIIndex.EmptyState).toBeDefined();
      expect(UIIndex.Field).toBeDefined();
      expect(UIIndex.HeroObject).toBeDefined();
      expect(UIIndex.Icon).toBeDefined();
      expect(UIIndex.Inspector).toBeDefined();
      expect(UIIndex.ListRow).toBeDefined();
      expect(UIIndex.LocalRail).toBeDefined();
      expect(UIIndex.MedicalTerm).toBeDefined();
      expect(UIIndex.Modal).toBeDefined();
      expect(UIIndex.PageShell).toBeDefined();
      expect(UIIndex.SectionIndex).toBeDefined();
      expect(UIIndex.SegmentedControl).toBeDefined();
      expect(UIIndex.Sheet).toBeDefined();
      expect(UIIndex.SourceDisclosure).toBeDefined();
      expect(UIIndex.StatusChip).toBeDefined();
      expect(UIIndex.Stepper).toBeDefined();
      expect(UIIndex.SurfaceCard).toBeDefined();
      expect(UIIndex.Tabs).toBeDefined();
      expect(UIIndex.Timeline).toBeDefined();
      expect(UIIndex.Toggle).toBeDefined();
    });
  });

  describe("components/shell modules (named and default exports)", () => {
    it("exports AdminPreviewBanner", () => {
      expect(AdminPreviewBanner).toBeDefined();
      expect(AdminPreviewBannerDefault).toBeDefined();
      expect(AdminPreviewBannerMod.AdminPreviewBanner).toBeDefined();
      expect(AdminPreviewBannerMod.default).toBeDefined();
    });

    it("exports PreviewContextStrip", () => {
      expect(PreviewContextStrip).toBeDefined();
      expect(PreviewContextStripDefault).toBeDefined();
      expect(PreviewContextStripMod.PreviewContextStrip).toBeDefined();
      expect(PreviewContextStripMod.default).toBeDefined();
    });

    it("exports ClaraOrb", () => {
      expect(ClaraOrb).toBeDefined();
      expect(ClaraOrbDefault).toBeDefined();
      expect(ClaraOrbMod.ClaraOrb).toBeDefined();
      expect(ClaraOrbMod.default).toBeDefined();
    });

    it("exports CommandPalette", () => {
      expect(CommandPalette).toBeDefined();
      expect(CommandPaletteDefault).toBeDefined();
      expect(CommandPaletteMod.CommandPalette).toBeDefined();
      expect(CommandPaletteMod.default).toBeDefined();
    });

    it("exports ChromeSurface", () => {
      expect(ChromeSurface).toBeDefined();
      expect(ChromeSurfaceDefault).toBeDefined();
      expect(ShellSurface).toBeDefined();
      expect(ChromeSurfaceMod.ChromeSurface).toBeDefined();
      expect(ChromeSurfaceMod.Surface).toBeDefined();
      expect(ChromeSurfaceMod.default).toBeDefined();
    });

    it("exports CommandPaletteProvider", () => {
      expect(CommandPaletteProvider).toBeDefined();
      expect(CommandPaletteProviderDefault).toBeDefined();
      expect(useCommandPaletteContext).toBeDefined();
      expect(CommandPaletteProviderMod.CommandPaletteProvider).toBeDefined();
      expect(CommandPaletteProviderMod.default).toBeDefined();
    });

    it("exports ConsumerLayout", () => {
      expect(ConsumerLayout).toBeDefined();
      expect(ConsumerLayoutDefault).toBeDefined();
      expect(ConsumerLayoutMod.ConsumerLayout).toBeDefined();
      expect(ConsumerLayoutMod.default).toBeDefined();
    });

    it("exports WorkspaceDock", () => {
      expect(WorkspaceDock).toBeDefined();
      expect(WorkspaceDockDefault).toBeDefined();
      expect(WorkspaceDockMod.WorkspaceDock).toBeDefined();
      expect(WorkspaceDockMod.default).toBeDefined();
    });

    it("exports FloatingPrimaryDock", () => {
      expect(FloatingPrimaryDock).toBeDefined();
      expect(FloatingPrimaryDockDefault).toBeDefined();
      expect(FloatingPrimaryDockMod.FloatingPrimaryDock).toBeDefined();
      expect(FloatingPrimaryDockMod.default).toBeDefined();
    });

    it("exports GlobalContextBar", () => {
      expect(GlobalContextBar).toBeDefined();
      expect(GlobalContextBarDefault).toBeDefined();
      expect(GlobalContextBarMod.GlobalContextBar).toBeDefined();
      expect(GlobalContextBarMod.default).toBeDefined();
    });

    it("exports PreferenceProvider", () => {
      expect(PreferenceProvider).toBeDefined();
      expect(PreferenceProviderDefault).toBeDefined();
      expect(usePreferences).toBeDefined();
      expect(PreferenceProviderMod.PreferenceProvider).toBeDefined();
      expect(PreferenceProviderMod.default).toBeDefined();
    });

    it("exports ProfessionalLayout", () => {
      expect(ProfessionalLayout).toBeDefined();
      expect(ProfessionalLayoutDefault).toBeDefined();
      expect(ProfessionalLayoutMod.ProfessionalLayout).toBeDefined();
      expect(ProfessionalLayoutMod.default).toBeDefined();
    });

    it("exports ProfileBoundary", () => {
      expect(ProfileBoundary).toBeDefined();
      expect(ProfileBoundaryDefault).toBeDefined();
      expect(useProfileBoundary).toBeDefined();
      expect(useProfileContext).toBeDefined();
      expect(ProfileBoundaryMod.ProfileBoundary).toBeDefined();
      expect(ProfileBoundaryMod.default).toBeDefined();
    });

    it("exports SessionBoundary", () => {
      expect(SessionBoundary).toBeDefined();
      expect(SessionBoundaryDefault).toBeDefined();
      expect(useSession).toBeDefined();
      expect(SessionBoundaryMod.SessionBoundary).toBeDefined();
      expect(SessionBoundaryMod.default).toBeDefined();
    });

    it("exports ShellModeProvider", () => {
      expect(ShellModeProvider).toBeDefined();
      expect(ShellModeProviderDefault).toBeDefined();
      expect(useShellMode).toBeDefined();
      expect(ShellModeProviderMod.ShellModeProvider).toBeDefined();
      expect(ShellModeProviderMod.default).toBeDefined();
    });

    it("barrel shell/index.ts exports all shell components without undefined", () => {
      expect(ShellIndex.AdminPreviewBanner).toBeDefined();
      expect(ShellIndex.PreviewContextStrip).toBeDefined();
      expect(ShellIndex.ChromeSurface).toBeDefined();
      expect(ShellIndex.Surface).toBeDefined();
      expect(ShellIndex.ClaraOrb).toBeDefined();
      expect(ShellIndex.CommandPalette).toBeDefined();
      expect(ShellIndex.CommandPaletteProvider).toBeDefined();
      expect(ShellIndex.ConsumerLayout).toBeDefined();
      expect(ShellIndex.WorkspaceDock).toBeDefined();
      expect(ShellIndex.FloatingPrimaryDock).toBeDefined();
      expect(ShellIndex.GlobalContextBar).toBeDefined();
      expect(ShellIndex.PreferenceProvider).toBeDefined();
      expect(ShellIndex.ProfessionalLayout).toBeDefined();
      expect(ShellIndex.ProfileBoundary).toBeDefined();
      expect(ShellIndex.SessionBoundary).toBeDefined();
      expect(ShellIndex.ShellModeProvider).toBeDefined();
    });
  });

  describe("components/admin modules (named and default exports)", () => {
    it("exports AdminShell", () => {
      expect(AdminShell).toBeDefined();
      expect(AdminShellDefault).toBeDefined();
      expect(AdminShellMod.AdminShell).toBeDefined();
      expect(AdminShellMod.default).toBeDefined();
    });

    it("exports AdminCommandStrip", () => {
      expect(AdminCommandStrip).toBeDefined();
      expect(AdminCommandStripDefault).toBeDefined();
      expect(AdminCommandStripMod.AdminCommandStrip).toBeDefined();
      expect(AdminCommandStripMod.default).toBeDefined();
    });

    it("exports AdminAppLauncherModal", () => {
      expect(AdminAppLauncherModal).toBeDefined();
      expect(AdminAppLauncherModalDefault).toBeDefined();
      expect(AdminAppLauncherModalMod.AdminAppLauncherModal).toBeDefined();
      expect(AdminAppLauncherModalMod.default).toBeDefined();
    });

    it("exports AdminOverviewPanel", () => {
      expect(AdminOverviewPanel).toBeDefined();
      expect(AdminOverviewPanelDefault).toBeDefined();
      expect(AdminOverviewPanelMod.AdminOverviewPanel).toBeDefined();
      expect(AdminOverviewPanelMod.default).toBeDefined();
    });

    it("exports AdminObservabilityPanel", () => {
      expect(AdminObservabilityPanel).toBeDefined();
      expect(AdminObservabilityPanelDefault).toBeDefined();
      expect(AdminObservabilityPanelMod.AdminObservabilityPanel).toBeDefined();
      expect(AdminObservabilityPanelMod.default).toBeDefined();
    });

    it("exports AdminAnswerFlowPanel", () => {
      expect(AdminAnswerFlowPanel).toBeDefined();
      expect(AdminAnswerFlowPanelDefault).toBeDefined();
      expect(AdminAnswerFlowPanelMod.AdminAnswerFlowPanel).toBeDefined();
      expect(AdminAnswerFlowPanelMod.default).toBeDefined();
    });

    it("exports AdminFlowDebugger", () => {
      expect(AdminFlowDebugger).toBeDefined();
      expect(AdminFlowDebuggerDefault).toBeDefined();
      expect(AdminFlowDebuggerMod.AdminFlowDebugger).toBeDefined();
      expect(AdminFlowDebuggerMod.default).toBeDefined();
    });

    it("exports AdminFlowRuntimePanel", () => {
      expect(AdminFlowRuntimePanel).toBeDefined();
      expect(AdminFlowRuntimePanelDefault).toBeDefined();
      expect(AdminFlowRuntimePanelMod.AdminFlowRuntimePanel).toBeDefined();
      expect(AdminFlowRuntimePanelMod.default).toBeDefined();
    });

    it("exports AdminFlowVisualizer", () => {
      expect(AdminFlowVisualizer).toBeDefined();
      expect(AdminFlowVisualizerDefault).toBeDefined();
      expect(AdminFlowVisualizerMod.AdminFlowVisualizer).toBeDefined();
      expect(AdminFlowVisualizerMod.default).toBeDefined();
    });

    it("exports AdminNeuralNetworkVisualizer", () => {
      expect(AdminNeuralNetworkVisualizer).toBeDefined();
      expect(AdminNeuralNetworkVisualizerDefault).toBeDefined();
      expect(AdminNeuralNetworkVisualizerMod.AdminNeuralNetworkVisualizer).toBeDefined();
      expect(AdminNeuralNetworkVisualizerMod.default).toBeDefined();
    });

    it("exports AdminAuditPanel", () => {
      expect(AdminAuditPanel).toBeDefined();
      expect(AdminAuditPanelDefault).toBeDefined();
      expect(AdminAuditPanelMod.AdminAuditPanel).toBeDefined();
      expect(AdminAuditPanelMod.default).toBeDefined();
    });

    it("exports AdminRagSourcesPanel", () => {
      expect(AdminRagSourcesPanel).toBeDefined();
      expect(AdminRagSourcesPanelDefault).toBeDefined();
      expect(AdminRagSourcesPanelMod.AdminRagSourcesPanel).toBeDefined();
      expect(AdminRagSourcesPanelMod.default).toBeDefined();
    });

    it("exports ProductAnalyticsPanel", () => {
      expect(ProductAnalyticsPanel).toBeDefined();
      expect(ProductAnalyticsPanelDefault).toBeDefined();
      expect(ProductAnalyticsPanelMod.ProductAnalyticsPanel).toBeDefined();
      expect(ProductAnalyticsPanelMod.default).toBeDefined();
    });

    it("exports ClinicalAnalyticsPanel", () => {
      expect(ClinicalAnalyticsPanel).toBeDefined();
      expect(ClinicalAnalyticsPanelDefault).toBeDefined();
      expect(ClinicalAnalyticsPanelMod.ClinicalAnalyticsPanel).toBeDefined();
      expect(ClinicalAnalyticsPanelMod.default).toBeDefined();
    });

    it("exports AnalyticsDateRange", () => {
      expect(AnalyticsDateRange).toBeDefined();
      expect(AnalyticsDateRangeDefault).toBeDefined();
      expect(AnalyticsDateRangeMod.AnalyticsDateRange).toBeDefined();
      expect(AnalyticsDateRangeMod.default).toBeDefined();
    });

    it("exports analytics primitives", () => {
      expect(PanelCard).toBeDefined();
      expect(KpiCard).toBeDefined();
      expect(BarList).toBeDefined();
      expect(TrendBars).toBeDefined();
    });

    it("exports useControlTowerConfig", () => {
      expect(useControlTowerConfig).toBeDefined();
      expect(useControlTowerConfigDefault).toBeDefined();
    });

    it("barrel admin/index.ts exports all admin components without undefined", () => {
      expect(AdminIndex.AdminShell).toBeDefined();
      expect(AdminIndex.AdminCommandStrip).toBeDefined();
      expect(AdminIndex.AdminAppLauncherModal).toBeDefined();
      expect(AdminIndex.AdminOverviewPanel).toBeDefined();
      expect(AdminIndex.AdminObservabilityPanel).toBeDefined();
      expect(AdminIndex.AdminAnswerFlowPanel).toBeDefined();
      expect(AdminIndex.AdminFlowDebugger).toBeDefined();
      expect(AdminIndex.AdminFlowRuntimePanel).toBeDefined();
      expect(AdminIndex.AdminFlowVisualizer).toBeDefined();
      expect(AdminIndex.AdminNeuralNetworkVisualizer).toBeDefined();
      expect(AdminIndex.AdminAuditPanel).toBeDefined();
      expect(AdminIndex.AdminRagSourcesPanel).toBeDefined();
      expect(AdminIndex.ProductAnalyticsPanel).toBeDefined();
      expect(AdminIndex.ClinicalAnalyticsPanel).toBeDefined();
      expect(AdminIndex.AnalyticsDateRange).toBeDefined();
      expect(AdminIndex.PanelCard).toBeDefined();
      expect(AdminIndex.useControlTowerConfig).toBeDefined();
    });
  });
});
