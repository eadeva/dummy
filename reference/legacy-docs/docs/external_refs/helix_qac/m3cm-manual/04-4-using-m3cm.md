# 4 | Using M3CM

4 | Using M3CM
Directives and Rules
MISRA C:2012 defined 159 guidelines made up of 16 directives and 143 rules.
n Amendment 1 - Additional security guidelines added 14 guidelines made up of 1 directive and 13 rules.
n Amendment 2 - Updates for ISO/IEC 9899:2011 Core Functionality added 2 guidelines both of which are rules.
n Amendment 3 - Updates for ISO/IEC 9899:2011 Phase 2 – New C11/C18 Features added 24 guidelines made up
of 1 directive and 23 rules.
n Amendment 4 - Updates for ISO/IEC 9899:2011 Phase 3 - Multi-threading and atomics added 22 guidelines
made up of 3 directives and 19 rules.
Therefore, MISRA C is now made up of 21 directives and 200 rules.
The guidelines are grouped into a number of sections, for example Compilation and Build, Code Design, Unused Code,
Types, Pointer Type Conversions, and so on.
The MISRA C document defines the distinction between a rule and a directive as follows:
"A rule is a guideline for which a complete description of the requirement has been provided. It should be
possible to check that source code complies with a rule without needing any other information. In particular,
static analysis tools should be capable of checking compliance with rules subject to the limitations
described in Section 6.5."
"A directive is a guideline for which it is not possible to provide the full description necessary to perform a
check for compliance. Additional information, such as might be provided in design documents or
requirements specifications, is required in order to be able to perform the check. Static analysis tools may
be able to assist in checking compliance with directives but different tools may place widely different
interpretations on what constitutes a non-compliance."
Rules are grouped according to whether they are Enforced or Unenforced. However, directives are considered to be
"Not Statically Enforceable (NSE)". Assistance is provided for some directives, but this may not be sufficient in itself to
ensure compliance in every situation. Where automatic help can be provided to ensure compliance, directives are
considered to be Assisted. Otherwise, they are considered to be Unassisted. Directives are grouped accordingly in
Rule Enforcement.
The directives are not taken into account in the Enforced/Unenforced Rules Percentages at the end of Rule
Enforcement, regardless of whether they are Assisted or Unassisted.
Configuring M3CM for Conformance to C90, C99 or C11
M3CM can be used for systems that conform to: C90, C99, C11 or a combination of the three. By default, M3CM is
configured to produce messages for systems conforming to the C99 standard, and, in this configuration, diagnostic
messages will be triggered wherever a feature not defined in the C99 standard is used.
M3CM5.6.0 is configured by default with the limits required by the C99 Language Standard. As such, -xnamelength
and -namelength use the component default values of 63 and 31 respectively, while the -po close_name::sig_
char option is explicitly set to 63.
Page 10


---
*Page 10*

Note:
In previous releases of M3CM, values for -namelength and -xnamelength set in CCTs, and not
explicitly overridden in the project, were used. In M3CM 5.6.0 this is no longer the case, and values set in
CCTs will not change the values from the C99 minimum required limits.
If the required language features and/or limits are different to those of C99, then analysis components can be configured
to reflect the required values:
QAC:
-namelength
-xnamelength
-ex LONGLONG
RCMA:
-po close_name::sig_char
The C11 minimum required limits are the same as those of C99. For strict enforcement to the C90 minimum required
limits, the -xnamelength and -po close_name::sig_char options should be set to six characters and the -
namelength option should be set to 31 characters.
The -ex option is cumulative and so it must first be reset using the -forgetall option. This can be achieved by adding
a .via file with the following content:
-forgetall ex
-ex asm
Some rules and use cases are not applicable to all variants of the language standard. As such, some Message Rule
Groups can be suppressed depending on the standard in use.
The Message Rule Groups for C90, C99, and C11 can be enabled or disabled as appropriate through the Rule
Configuration settings of the Project Properties.
C90
Enable message groups:
M3CM-1-C90 MISRA Mandatory
M3CM-2-C90 MISRA Required
M3CM-3-C90 MISRA Advisory
Page 11


---
*Page 11*

C90
Disable message groups:
M3CM-1-C99 MISRA Mandatory
M3CM-2-C99 MISRA Required
M3CM-3-C99 MISRA Advisory
M3CM-1-C99-C11 MISRA Mandatory
M3CM-2-C99-C11 MISRA Required
M3CM-3-C99-C11 MISRA Advisory
M3CM-1-C11 MISRA Mandatory
M3CM-2-C11 MISRA Required
M3CM-3-C11 MISRA Advisory
C99
Enable message groups:
M3CM-1-C99 MISRA Mandatory
M3CM-2-C99 MISRA Required
M3CM-3-C99 MISRA Advisory
M3CM-1-C99-C11 MISRA Mandatory
M3CM-2-C99-C11 MISRA Required
M3CM-3-C99-C11 MISRA Advisory
Disable message groups:
M3CM-1-C90 MISRA Mandatory
M3CM-2-C90 MISRA Required
M3CM-3-C90 MISRA Advisory
M3CM-1-C11 MISRA Mandatory
M3CM-2-C11 MISRA Required
M3CM-3-C11 MISRA Advisory
C11
Enable message groups:
M3CM-1-C99-C11 MISRA Mandatory
M3CM-2-C99-C11 MISRA Required
M3CM-3-C99-C11 MISRA Advisory
M3CM-1-C11 MISRA Mandatory
M3CM-2-C11 MISRA Required
M3CM-3-C11 MISRA Advisory
Page 12


---
*Page 12*

C11
Disable message groups:
M3CM-1-C90 MISRA Mandatory
M3CM-2-C90 MISRA Required
M3CM-3-C90 MISRA Advisory
M3CM-1-C99 MISRA Mandatory
M3CM-2-C99 MISRA Required
M3CM-3-C99 MISRA Advisory
See the Component and Helix QAC manuals for more details.
Configuring M3CM for Use with Amendments
MISRA C guidelines are made up of MISRA C:2012 plus:
n Amendment 1 - Additional security guidelines for MISRA C:2012
n Amendment 2 - Updates for ISO/IEC 9899:2011 Core Functionality
n Amendment 3 – Updates for ISO/IEC 9899:2011 Phase 2 – New C11/C18 Features
n Amendment 4 - Updates for ISO/IEC 9899:2011 Phase 3 - Multi-threading and atomics
M3CM is configured by default to produce messages for MISRA C guidelines (or MISRA C:2012 plus all amendments).
If required, the configuration can be modified to support MISRA C:2012 plus individual amendments. However, these
must be applied in reverse order.
Amendment 4 - Updates for ISO/IEC 9899:2011 Phase 3 - Multi-threading and
atomics
The default configuration for M3CM is C99 and has 4 rules associated with Amendment 4 - Updates for ISO/IEC
9899:2011 Phase 3 - Multi-threading and atomics: Rule 2.8, Rule 7.6. Rule 9.6, Rule 18.10.
To configure for C90, the following rules should be disabled: Rule 7.6, Rule 9.6, Rule 18.10.
The following rules apply to C11 only and are disabled by default: Dir 5.1, Dir 5.2, Dir 5.3, Rule 9.7, Rule 11.10, Rule
12.6, Rule 21.25, Rule 21.26. Rules 22.11-22.20.
To remove the changes in Amendment 4 - Updates for ISO/IEC 9899:2011 Phase 3 - Multi-threading and atomics and
revert to Amendment 3 - disable the following: Rule 2.8, Rule 7.6. Rule 9.6, Rule 18.10.
Amendment 3 – Updates for ISO/IEC 9899:2011 Phase 2 – New C11/C18 Features
The default configuration for M3CM is C99 and has 9 rules associated with Amendment 3 – Updates for ISO/IEC
9899:2011 Phase 2 – New C11/C18 Features: Rule 1.5, Rule 6.3, Rule 7.5, Rule 17.12, Rule 17.13, Rule 18.9, Rule
21.22, Rule 21.23, Rule 21.24.
To configure for C90, the following rules should be disabled Rule 1.5, Rule 7.5, Rule 21.22, Rule 21.23.
The following rules apply to C11 only and are disabled by default:  Rule 8.15, Rule 8.16, Rule 8.17, Rule 17.9, Rule
17.10, Rule 17.11, Rule 23.1 – Rule 23.8.
Page 13


---
*Page 13*

To remove the changes in Amendment 3 – Updates for ISO/IEC 9899:2011 Phase 2 – New C11/C18 Features and revert
to Amendment 2 – disable the following: Rule 1.5, Rule 6.3, Rule 7.5, Rule 17.12, Rule 17.13, Rule 18.9, Rule 21.22,
Rule 21.23, Rule 21.24.
Additionally, recategorize Rule 21.11 back to Required from Advisory and Rule 21.12 back to Advisory from Required.
Note:
Headlines will not change back to previous text.
For C11 only, to remove the Amendment 3 changes to Rule 1.4, add messages 1077, 1078, 1079 1082.
Amendment 2 - Updates for ISO/IEC 9899:2011 Core Functionality
There are 2 rules associated with Amendment 2 Updates for ISO/IEC 9899:2011 Core Functionality: Rule 1.4 and Rule
21.21 plus an update to Rule 21.8.
Rule 1.4 is applicable to C11 only and is therefore disabled by default.
To remove the changes made for Amendment 2: Updates for ISO/IEC 9899:2011 Core Functionality disable Rule 21.21
and in Rule 21.8 enable message 5150.
Amendment 1 - Additional security guidelines for MISRA C:2012
There are 14 guidelines associated with Amendment 1 – Directive 4.14, Rules 12.5, Rules 21.13-21.20, Rules 22.7-
22.10. To remove the changes for Amendment 1 and revert to MISRA C:2012 , these guidelines should be disabled. Also
re-enable message 5128 in Rule 21.8.
Configuration of Rule-20.5 - #undef Shall Not Be Used
Messages 0841 which only applies to active use of #undef is mapped to Rule 20.5.
Message 0847 was added to the mapping in Helix QAC 2022.4, and applies to the use of #undef in a conditionally-
excluded block.
However, for a given configuration, message 0847 will not affect the safety case as the code will not be executed. (it may
only assist if the configuration changes). As the message could be noisy, it has been disabled by default. It can be re-
enabled by changing to mapped="yes" in rcf.
The Helix QAC for C Message System
Each MISRA C guideline is classified as Mandatory, Required or Advisory, and this classification is reflected in the
structure of the message system.
This classification can be defined as follows:
n Mandatory guidelines: C Code must comply with every guideline to conform to the MISRA C standard.
Deviations are not permitted.
Note:
If a static analysis tool such as Helix QAC for C produces a diagnostic message, this does not
necessarily mean that a guideline has been violated (for the reasons given in Section 6.5 of the
MISRA C document).
Page 14


---
*Page 14*

n Required guidelines: C Code must comply with every guideline to conform to the MISRA C standard with a
formal deviation required if this is not possible.
n Advisory guidelines: These are recommendations, but it does not mean that they can be ignored, and they
should be followed as far as is reasonably practicable. Formal deviations are not required, but, in this event,
alternative arrangements should be made for documenting non-compliance.
The M3CM messages used by Helix QAC for C to enforce the above message system are arranged into the following
groups:
Common
Information
Errors
MISRA Mandatory
Rules
MISRA Required
Rules
Directives
MISRA Advisory
Rules
Directives
Each Rules and Directives sub-group contains one or more MISRA C guidelines, with an associated Helix QAC for C
message group corresponding to each enforceable guideline.
The Common message group contains messages from the Helix QAC for C and RCMA Information message groups,
and from the Helix QAC for C Errors message group - for these messages, you should refer to the Default Rule
Configuration File supplied with Helix QAC.
Mapping Messages to MISRA Directives and Rules
A guideline may be enforced by one or all of the following:
n Helix QAC for C Primary Analysis
n M3CM Secondary Analysis
n RCMA (Relational Cross-Module Analysis)
n Some combination of all the above elements.
Some analysis messages are associated with more than one MISRA guideline. This occurs when:
n The requirements of two MISRA guidelines overlap. For example, any violation of Rule 11.7 ("A cast shall not be
performed between pointer to object and a noninteger arithmetic type") will also violate Rule 1.3. Or
n The granularity of the condition identified by an analysis message does not coincide uniquely with a single MISRA
guideline. For example, message 0306 ("Cast between a pointer to object and an integral type.") is mapped to
both Rule 11.4 ("A conversion should not be performed between a pointer to object and an integer type") and
Rule 11.6 ("A cast shall not be performed between pointer to void and an arithmetic type"). Or
Page 15


---
*Page 15*

n The violation of one rule results in the violation of another rule. For example, Rule 5.8 ("Identifiers that define
objects or functions with external linkage shall be unique") may also result in the violation of Rule 5.9 ("Identifiers
that define objects or functions with internal linkage should be unique").
The guideline(s) with which each message is associated will always be reported in the "reference text". However, in the
rare situations where a message is associated with more than one guideline, it will only be specifically mapped to one of
the guidelines - the primary one. Where this situation occurs, any statistics relating to the number of violations of any
particular guideline may be slightly misleading.
Note:
If a message that is mapped to more than one guideline is suppressed, it will be suppressed for all the
guidelines with which it is associated.
Page 16


---
*Page 16*

Global Checks
Cross-Module Analysis checks are required to fully implement a compliance modules rule set. This analysis is normally
only of significant value when the code from a complete project is available for analysis.
For details of the configuration and use of Cross-Module Analysis, please refer to the RCMA Manual.
Page 17


---
*Page 17*
