# 1 | Helix QAC for C Overview

1 | Helix QAC for C Overview
Helix QAC for C is a deep flow static analysis tool for C code.  Helix QAC for C is designed to help you to improve the
quality of your software development.
Helix QAC for C analyzes source code on a file-by-file basis to identify unsafe usage of the C language. A library of over
1650 warning messages is used to highlight source code that is non-portable, difficult to maintain, overly complex, or
written in any way that is likely to cause vulnerabilities or other problems.
The tool specifically identifies language usage which is not compliant with the ISO C90 standard (ISO/IEC 9899:1990) or
relies on unspecified, undefined or implementation-defined behavior. The tool warns when features specific to the ISO
C99 standard are used, and supports the semantics of some of these features.
The tool also produces code metrics, which provide a quantifiable measure of code attributes. Further information
provided by  Helix QAC for C can be used to generate reports and perform Cross-Module Analysis.
Analysis Overview
The input to  Helix QAC for C consists of one or more source files to be analyzed, together with any files that are included
by the analyzed files, whether directly or indirectly and a set of configuration options that determine analysis settings for
both the overall compiler and the particular project.
The output from  Helix QAC for C consists of generated messages written to the Helix QAC database, an .arc file that
contains metrics information and other information to support Cross-Module Analysis, and an optional .i file that contains
the preprocessed source code.
Analysis is performed in three phases:
 n Primary analysis is provided by  Helix QAC for C, which delivers the majority of language analysis in the product.
 n Cross-Module Analysis (RCMA1) covers a range of checks that operate across translation units following primary
analysis. Refer to the RCMA Component Manual.
 n Secondary analysis constitutes optional, user-configurable add-ons, typically containing checks that are
designed to help enforce specific coding standards via different Compliance Modules. Refer to the individual
Compliance Module component manuals.
By configuring  Helix QAC for C appropriately, with the additional assistance of RCMA and secondary analyses, a high
degree of enforcement to various coding standards can be achieved, in parallel with the detection of bugs and serious
issues.
1The "R" is for Relational and differentiates this version from the previous memory-based implementation of CMA.
Page 14


---
*Page 14*
