# 3 | RCMA Configuration

3 | RCMA Configuration
Configuring RCMA
RCMA Configuration options can be grouped based on:
n Type of Analysis
n Message Suppression
n Output
n Auxiliary Options
Type of Analysis
Option
Effect
Metrics
-threshold
Output the specified message whenever the threshold for
specified metric is exceeded.
Member Encapsulation Ratio
-prodoption class::member_encapsulation_ratio
Threshold setting for ratio between members and
getters/setters.
Similar Name Analysis
-prodoption close_name::similar
Characters to be considered as identical when matching
identifiers.
-prodoption close_name::ignore
Characters to be ignored when matching identifiers.
-prodoption close_name::any_case
Case to be ignored when matching identifiers.
Significant Characters Analysis
-prodoption close_name::sig_char
Maximum length within which two identifiers must be unique.
Metrics
A threshold can be set for a metric using the -threshold configuration option. If the metric is not within the threshold, then
a diagnostic will be issued.
See Metric Thresholds
Member Encapsulation Ratio
When the -prodoption class:member_encapsulation_ratio option is set, RCMA will calculate the ratio of members to
public getters/setters using the following formula:
Page 8


---
*Page 8*

n = Number of private or protected members. m = Number of private or protected
members with a public Getter or Setter function.
See RCMA help for message 1760 for more information and examples.
Similar Name Analysis
RCMA provides functionality to warn when identifiers for two distinct entities are named in such a way that one could be
mistaken for the other:
int FOO;
int F00; /* Could be confused with FOO */
See the -prodoption close_name::similar, -prodoption close_name::ignore and -prodoption close_name::any_case
configuration settings.
Message Suppression
Messages can be suppressed on the command line directly, or with annotations added to the source code. The following
configuration options control message suppression on the command line:
Option
Effect
Message Suppression
-only
Generate only the specified warning messages
-nomsg
Suppress the generation of specified messages
Comment-Based Suppressions
RCMA diagnostics are suppressed for comment-based suppressions as these are applied at view time and are based
purely on the message numbers and locations of the diagnostics.
Output
Option
Effect
Output
-outputpath
Location where primary analysis output files are found
-echo
Specifies that text is echoed to the console
Page 9


---
*Page 9*

Option
Effect
-metrics
Whether analysis data is written to the metric output file
-settings
Print current values for all configuration options
-version
Print the version number for the executable
Auxiliary Options
Option
Effect
Auxiliary
-via
Read configuration options from the specified file
-forgetall
Reset previous configuration settings for option
Page 10


---
*Page 10*
