# 3 | M3CM Components

3 | M3CM Components
Having installed the supplied software, you will need to make changes to the configuration of existing projects. By using
the M3CM configuration, the analysis will be reconfigured to use the following:
n A subset of the Helix QAC for C messages appropriate to enforcement of the MISRA C guidelines.
n A new message structure reflecting the MISRA C guidelines.
n Secondary analysis checks to enforce a number of the MISRA C guidelines.
Dataflow
When you select the M3CM component, Dataflow Analysis is automatically enabled in order to provide a basic level of
MISRA C enforcement and function inlining. If you wish to enhance the level of analysis, then the simplest way to do this
is to select a preset Dataflow Depth for the associated Helix QAC for C component in Helix QAC, using the Dataflow
Settings drop-down in the Project Properties’ Analysis pane.
Note:
While there are no configuration requirements specific to M3CM enforcement, an appropriate
configuration depends on factors such as the hardware environment and the complexity of the code. This
is especially important where consistency of results is required over different hardware configurations.
Further details can be found in the Helix QAC for C and Dataflow Component Manuals.
Page 9


---
*Page 9*
