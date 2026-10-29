# 4 | Running RCMA

4 | Running RCMA
RCMA differs from PRQA’s other analysis components, Helix QAC for C and Helix QAC for C++, in that it can
simultaneously analyze several projects, operating across the multiple translation units that make up a linkable entity.
The option used to set up such analysis is the CMA Project Editor, and you should refer to this option in the Helix QAC,
Helix QAC Eclipse or Helix QAC Visual Studio user guide, as appropriate.
RCMA Workflow
Semantic information from the translation units is first stored in the RCMA database before analysis takes place. As well
as improved performance for large projects, use of the database helps ensure the integrity of the stored data.
Conceptually, RCMA has the following three steps:
1. Population of Semantic Information
2. Analysis Checks
3. Generation of Metrics
Population of Semantic Information
The primary analyzers, Helix QAC for C and Helix QAC for C++, store detailed semantic information for the analyzed
translation units in individual .arc files. See Input Files.
This information includes details such as:
n Headers included,
n Identifiers declared,
n Function call trees.
The first phase of RCMA reads and merges the information produced for each individual translation unit and stores it in
the database where the analysis checks and metric generation can take place.
All information for a given translation unit can be removed or updated. A checksum is used to ensure that a file is
populated only if its contents have changed. Any previous content for a file will be removed before it is populated with the
new contents.
Analysis Checks
Analysis checks are performed over the merged model of a project’s translation units. Any diagnostics will be written to
the Helix QAC database, with metrics being written to the Cross-Module Analysis .arc file. See Output Files.
The complete set of messages are listed in RCMA Messages.
Generation of Metrics
Project-wide metrics are generated against the merged model of a project’s translation units, and written to the Cross-
Module Analysis .arc file. See Output Files.
The complete set of RCMA metrics are listed in Metrics.
Page 11


---
*Page 11*

Cross Module Analysis I/O
Input Files
RCMA uses the .arc files created by the primary and secondary analysis phases as the input for its analysis.
The location used by RCMA when searching for the output from the previous analysis phases is:
1. The path specified using -outputpath if set; or
2. The path specified by the environment variables QACOUTPATH (for Helix QAC for C) or QACPPOUTPATH (for
Helix QAC for C++) if set; or
3. The current working directory.
The specified path must be a directory and must be able to be read by the RCMA process.
Output Files
RCMA writes diagnostic records to the Helix QAC database and generates .arc) files.
The prefix and path for the .arc and other project-wide output files are specified using -crossmoduleanalysisfile in
Configuration Options.
The specified path must be a directory and must be able to be written to by the RCMA process. If no path is specified,
then output is sent to the current working directory.
Page 12


---
*Page 12*
