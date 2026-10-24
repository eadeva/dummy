"""Factory helpers for reporting_v2 pipeline assembly."""

from xc_ce_utils.core_engine.reporting.adapters.exporters import (
    GitHubSummaryExporter,
    HtmlReportExporter,
    JsonReportExporter,
    JUnitReportExporter,
    MarkdownReportExporter,
)
from xc_ce_utils.core_engine.reporting.adapters.importers import (
    Arch2NeedsImporter,
    BuildContextImporter,
    CanoeTestReportImporter,
    CanonicalJsonImporter,
    CoberturaCoverageImporter,
    ConfigImporter,
    CycloneDxImporter,
    DependenciesImporter,
    ExecutionStepImporter,
    GcovrSummaryImporter,
    JUnitXmlImporter,
    LogFindingsJsonImporter,
    NeedsAnalysisImporter,
    QacCsvImporter,
    SbomDiscoveryImporter,
    SonarQubeCoverageImporter,
    StaticFindingsSummaryImporter,
    TacoImporter,
)
from xc_ce_utils.core_engine.reporting.application.use_cases import (
    ReportingPipeline,
)


def build_default_reporting_pipeline() -> ReportingPipeline:
    """Build the default v2 pipeline with builtin import/export adapters."""
    importers = [
        ExecutionStepImporter(),
        DependenciesImporter(),
        BuildContextImporter(),
        CycloneDxImporter(),
        SbomDiscoveryImporter(),
        NeedsAnalysisImporter(),
        Arch2NeedsImporter(),
        TacoImporter(),
        LogFindingsJsonImporter(),
        JUnitXmlImporter(),
        CanoeTestReportImporter(),
        CanonicalJsonImporter(),
        CoberturaCoverageImporter(),
        SonarQubeCoverageImporter(),
        GcovrSummaryImporter(),
        QacCsvImporter(),
        StaticFindingsSummaryImporter(),
        ConfigImporter(),
    ]
    exporters = [
        JsonReportExporter(),
        JUnitReportExporter(),
        HtmlReportExporter(),
        MarkdownReportExporter(),
        GitHubSummaryExporter(),
    ]
    return ReportingPipeline(importers=importers, exporters=exporters)
