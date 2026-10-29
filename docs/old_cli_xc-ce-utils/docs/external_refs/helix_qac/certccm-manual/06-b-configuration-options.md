# B | Configuration Options

B | Configuration Options
-echo,-e
Syntax:
-echo text
Default:
no entry
Category:
Advanced
Function:
Specifies that text is echoed to the console.
This option can be used to show the configuration files that are being referenced.
-forgetall,-forget,-f
Syntax:
-forgetall option
Default:
no entry
Category:
Advanced
Function:
Resets previous configuration settings for option.
Some options are cumulative in their action in that successive usage of the option adds extra settings rather than
replacing the previous ones.
For example:
... -q path1 -q path2 -forgetall q -q path3 filename
For this argument list, the path1 and path2 options will be discarded and only path3 will be quieted.
The following options are cumulative in CERTCCM:
n -nomsg,-no,-n
n -only,-o
n -quiet,-q
-help,-h
Syntax:
-help[{+|-}]
Default:
-help-
Category:
Internal
Function:
When enabled, a basic help description for the component and its available configuration options is
displayed.
Page 41


---
*Page 41*

-namerulefile,-nrf
Syntax:
-namerulefile filename
Default:
no entry
Category:
Basic
Function:
Specifies the file containing the naming convention rules to be applied by namecheck.
The name rules file contains the rules to be used by the Name Checker. As a minimum, each rule should specify the
pattern (Regular Expression) that is to be applied to each type of identifier (macros, functions, typedefs, variables, etc).
You can have different rules for different types of identifier.
See the Configuration File section of the Namecheck user manual.
-nomsg,-no,-n
Syntax:
-nomsg message_number_list
Default:
no entry
Category:
Non-component
Function:
Suppresses the display and generation of the specified messages.
Message numbers can be specified individually, or as a list, range or a combination of both:
n -nomsg 2356
n -nomsg 1234,1236,1240
n -nomsg 2111,2200-2300
Note:
This option is only available at the file or directory level. The enabling or disabling of diagnostics at the
component level is managed through the Rule Configuration File (RCF).
This option is cumulative. See -forgetall,-forget,-f.
-only,-o
Syntax:
-only message_number_list
Default:
no entry
Category:
Non-component
Function:
Only the specified warning messages will be generated.
Page 42


---
*Page 42*

Message numbers can be specified individually, or as a list, range or a combination of both:
n -only 2356
n -only 1234,1236,1240
n -only 2111,2200-2300
Note:
This option is only available at the file or directory level. The enabling or disabling of diagnostics at the
component level is managed through the Rule Configuration File (RCF).
This option is cumulative. See -forgetall,-forget,-f.
-outputpath,-op
Syntax:
-outputpath path
Default:
no entry
Category:
Internal
Function:
Determines the path to which all output files will be generated during analysis, and, by extension, the
location from which all files will be read as the input for RCMA analysis.
See the "Analyzing Source Code" section of the Helix QAC for C or Helix QAC for C++ user manual, as appropriate.
-prodoption,-paloption,-qacppoption,-qo,-po
Syntax:
-prodoption argument
Default:
no entry
Category:
Advanced
Function:
Enables fine-grained configuration of analysis.
prodoption is used to provide additional fine-grained configuration to the analysis performed by a component.
-quiet,-q
Syntax:
-quiet filename|path
Default:
no entry
Category:
Basic
Function:
Suppresses the generation of diagnostic and metrics output for the specified file or files in the specified
path.
Page 43


---
*Page 43*

This will have the effect of suppressing warning messages as well as significantly reducing the size of the output
produced.
Note:
This option applies only to included files and has no effect on the main source file.
Note:
This option should not be used for project header files or directories, as it may affect the results of CMA,
Project Metrics and Reports.
This option is cumulative, see -forgetall,-forget,-f.
-quietextended,-qx
Syntax:
-quietextended filename|path
Default:
no entry
Category:
Basic
Function:
Suppresses the generation of diagnostic output for unused contents of the specified file or files in the
specified path.
This will have the effect of suppressing warning messages as well as significantly reducing the size of the output
produced. This suppression is limited to constructs from those files/folders that are not used in non suppressed files.
When the argument is a non-absolute path, the path is interpreted to be a regular file path relative to a -systeminclude
path. If the concatenation of a system include path and the relative file path corresponds to an existing file, the option
takes effect on that file.
Note:
This option applies only to included files and has no effect on the main source file.
This option is cumulative, see -forgetall,-forget,-f.
-remark,-rem
Syntax:
-remark comment
Default:
no entry
Category:
Advanced
Function:
The -remark option can be used to add additional comments into configuration files. Alternatively,
comments can be included in the configuration files by prefixing the comments with an asterisk.
Page 44


---
*Page 44*

-settings,-set
Syntax:
-settings[{+|-}]
Default:
-settings-
Category:
Internal
Function:
Print the settings used by the tool after the complete processing of all command line arguments.
When enabled, the current values for all configuration options are listed to the standard output.
-url
Syntax:
-url url
Default:
no entry
Category:
Internal
Function:
The URL of the server to which analysis data should be sent.
If no -url is specified, then output will be sent to the legacy output formats.
-version,-ver,-v
Syntax:
-version[{+|-}]
Default:
-version-
Category:
Internal
Function:
When enabled, the version number is printed to standard out and the tool will exit immediately.
-via
Syntax:
-via file
Default:
no entry
Category:
Advanced
Function:
Used to specify a file containing additional configuration options.
Page 45


---
*Page 45*

-virtualmemorylimit,-vml
Syntax:
-virtualmemorylimit value
Default:
-virtualmemorylimit 70
Category:
Advanced
Function:
Determines the limit on the available memory a component can utilise.
Before analysis is performed by a component a limit is set on the amount of memory that the component can utilise. By
default this limit is set to either a percentage of the systems physical memory or a default fixed size, whichever is largest.
This option determines the limit placed on the memory available to the component during analysis as a percentage of the
total systems memory.
If the argument of this option is 0 then no memory limit is applied to the component. And if the value of the argument does
not lie between 0 and 100 then the default limit will be applied.
Page 46


---
*Page 46*
