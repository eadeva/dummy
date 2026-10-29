# 1 |  Helix QAC for C++ Overview

1 | Helix QAC for C++ Overview
Helix QAC for C++ is a deep flow static analyzer for C++ code and is designed to help you improve the quality of your
software.
Helix QAC for C++ analyzes source code on a file-by-file basis to identify dangerous usage of the C++ language. A
library of over 1500 warning messages is used to highlight source code which is non-portable, difficult to maintain, overly
complex, or written in any way that is likely to cause problems.
The tool will also identify language usage which is not compliant with the modern ISO
C++ standards ISO/IEC 14882:2014(E) and ISO/IEC 14882:2011(E), their predecessor ISO/IEC 14882:1998(E) and
technical corrigendum ISO/IEC 14882:2003, or language use that is classified as giving rise to unspecified, undefined or
implementation-defined behavior.
Combined with other components, the overall solution provides:
n Code metrics that provide a quantifiable measure of code attributes: 29 functionbased, 16 file-based, and 8 class-
based;
n Function structure diagrams to provide an insight into control flow;
n Relationship diagrams to demonstrate function calling, global referencing, include file trees, class hierarchies,
and class implementation details;
n Cross-Module Analysis capability, pinpointing memory allocation mismatches, function recursion, and other
project wide issues;
n Baselining capability to simplify modification of legacy code.
Analysis Overview
The input to Helix QAC for C++ consists of one or more source files to be analyzed, together with any files that are
included by the analyzed files, whether directly or indirectly and a set of configuration options that determine analysis
settings for both the overall compiler and the particular project.
The output from Helix QAC for C++ consists of generated messages written to the Helix QAC database, an .arc file that
contains metrics information and other information to support Cross-Module Analysis, and an optional .i file that contains
the preprocessed source code.
Analysis is performed in three phases:
n Primary analysis is provided by Helix QAC for C++ , which delivers the majority of language analysis in the
product.
n Cross-Module Analysis (RCMA1) covers a range of checks that operate across translation units following primary
analysis. Refer to the RCMA Component Manual.
n Secondary analysis constitutes optional, user-configurable add-ons, typically containing checks that are
designed to help enforce specific coding standards via different Compliance Modules. Refer to the individual
Compliance Module component manuals.
1The "R" is for Relational and differentiates this version from the previous memory-based implementation of CMA.
Page 15


---
*Page 15*

By configuring Helix QAC for C++ appropriately, with the additional assistance of RCMA and secondary analyses, a high
degree of enforcement to various coding standards can be achieved, in parallel with the detection of bugs and serious
issues.
Page 16


---
*Page 16*
