# Important Notice

Important Notice
Change of Company Ownership
Programming Research Ltd., also known as “PRQA”, became a wholly owned subsidiary of Perforce Software Inc., also
known as “Perforce”, in May 2018.
Disclaimer of Warranty
This document should only be used in conjunction with M3CM.
Programming Research Ltd have taken due care in preparing this document which it has endeavored to ensure is
accurate at the time of printing. However, no liability can be accepted for errors or omissions; nor should the document
be considered as an expressed or implied warranty of accuracy or completeness, fitness for a particular purpose, or that
the products described perform as specified within.
Copyright Notice
All rights reserved. No part of this document may be reproduced, stored in a retrieval system of any nature, or transmitted
in any form or by any means, including photocopying and recording, without the prior written permission of Programming
Research Ltd., the copyright owner. If any unauthorized acts are carried out in relation to this copyrighted work, a civil
claim for damages may be made and/or a criminal prosecution may result. Copyright ©Programming Research Ltd 2024.
Trademarks
Helix QAC, the Helix QAC logo, Helix QAC for C, Helix QAC for C++ and High Integrity C++ (HIC++) are trademarks of
Programming Research Ltd.
"MISRA", "MISRA C" and "MISRA C++" are registered trademarks of The MISRA Consortium Limited.
"AUTOSAR" is a registered trademark of AUTOSAR GbR, held on behalf of the AUTOSAR Development Partnership.
"CERT" is a registered trademark of Carnegie Mellon University.
Yices is a registered trademark of SRI International.
Windows is a registered trademark of Microsoft Corporation.
Page 2


---
*Page 2*

Contacting Programming Research Ltd
For technical support, contact your nearest Programming Research Ltd. authorized distributor or, alternatively, the
Programming Research Ltd head office as follows
by telephone on +44 (0) 1189 771020
by fax on +1 612.688.7455
or by webpage: https://www.perforce.com/support/request-support
Page 3


---
*Page 3*

Contents
Important Notice
2
Change of Company Ownership
2
Disclaimer of Warranty
2
Copyright Notice
2
Trademarks
2
Contacting Programming Research Ltd
3
1 | Introduction
7
THE MISRA C Compliance Module
7
2 | Installation
8
Windows Installation
8
Linux Installation
8
3 | M3CM Components
9
Dataflow
9
4 | Using M3CM
10
Directives and Rules
10
Configuring M3CM for Conformance to C90, C99 or C11
10
Configuring M3CM for Use with Amendments
13
Amendment 4 - Updates for ISO/IEC 9899:2011 Phase 3 - Multi-threading and atomics
13
Amendment 3 – Updates for ISO/IEC 9899:2011 Phase 2 – New C11/C18 Features
13
Amendment 2 - Updates for ISO/IEC 9899:2011 Core Functionality
14
Amendment 1 - Additional security guidelines for MISRA C:2012
14
Configuration of Rule-20.5 - #undef Shall Not Be Used
14
The Helix QAC for C Message System
14
Mapping Messages to MISRA Directives and Rules
15
Global Checks
17
5 | Rule Enforcement
18
CSV Rule Summary
18
MISRA Mandatory
18
Rules
18
MISRA Mandatory
20
C11 Specific Rules
20
MISRA Mandatory
21
C90 Specific Rules
21
Page 4


---
*Page 4*

MISRA Mandatory
21
C99 and C11 Specific Rules
21
MISRA Required
22
Rules
22
Directives
37
MISRA Required
38
C11 Specific Rules
38
C11 Specific Directives
40
MISRA Required
40
C90 Specific Rules
40
C90 Specific Directives
41
MISRA Required
41
C99 Specific Rules
41
C99 Specific Directives
42
MISRA Required
42
C99 and C11 Specific Rules
42
MISRA Advisory
44
Rules
44
Directives
48
MISRA Advisory
49
C11 Specific Rules
49
MISRA Advisory
50
C90 Specific Rules
50
MISRA Advisory
50
C99 Specific Rules
50
MISRA Advisory
50
C99 and C11 Specific Rules
50
Rule Enforcement Summary
51
A | Program Return Codes
52
B | Configuration Options
53
-echo,-e
53
-forgetall,-forget,-f
53
-help,-h
53
-namerulefile,-nrf
54
Page 5


---
*Page 5*

-nomsg,-no,-n
54
-only,-o
54
-outputpath,-op
55
-prodoption,-paloption,-qacppoption,-qo,-po
55
-quiet,-q
55
-quietextended,-qx
56
-remark,-rem
56
-settings,-set
57
-slashwhite,-sl
57
-url
57
-version,-ver,-v
57
-via
58
-virtualmemorylimit,-vml
58
Page 6


---
*Page 6*
