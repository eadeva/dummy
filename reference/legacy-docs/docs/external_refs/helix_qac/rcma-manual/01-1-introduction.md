# 1 | Introduction

1 | Introduction
Cross-Module Analysis (RCMA1) is an analysis component designed to operate within the Helix QAC component.
RCMA augments the analysis performed by Helix QAC for C and Helix QAC for C++ by performing project-wide analysis.
Unlike Helix QAC for C and Helix QAC for C++, RCMA operates over multiple translation units highlighting issues
normally only detectable during link-time. RCMA makes available approximately 60 additional warning messages,
highlighting code that is non-portable, difficult to maintain, or results in a program being ill-formed or having undefined
behavior.
In addition to this analysis, RCMA includes 11 project-wide metrics:
n 6 metrics common to both the C and C++ languages; and
n 5 metrics specific to the C++ language.
Analysis Overview
Analysis is performed in three phases:
n Primary analysis is provided by Helix QAC for C and Helix QAC for C++, which deliver the majority of language
analysis.
n RCMA covers a range of checks that operate across translation units following primary analysis.
n Secondary analysis constitutes optional, user-configurable add-ons, and typically contains checks that are
industry, company or standards-specific. Refer to the individual compliance module component manuals.
By suitable configuration of each phase, a high degree of automatic enforcement to various coding standards can be
achieved, in parallel with the detection of bugs and serious issues.
1The "R" is for Relational and differentiates more recent versions from the previous memory-based implementation of CMA.
Page 6


---
*Page 6*
