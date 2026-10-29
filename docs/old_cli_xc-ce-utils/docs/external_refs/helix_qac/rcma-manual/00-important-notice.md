# Important Notice

Important Notice
Change of Company Ownership
Programming Research Ltd., also known as “PRQA”, became a wholly owned subsidiary of Perforce Software Inc., also
known as “Perforce”, in May 2018.
Disclaimer of Warranty
This document should only be used in conjunction with RCMA.
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
6
Analysis Overview
6
2 | RCMA Installation
7
3 | RCMA Configuration
8
Configuring RCMA
8
Type of Analysis
8
Metrics
8
Member Encapsulation Ratio
8
Similar Name Analysis
9
Message Suppression
9
Comment-Based Suppressions
9
Output
9
Auxiliary Options
10
4 | Running RCMA
11
RCMA Workflow
11
Population of Semantic Information
11
Analysis Checks
11
Generation of Metrics
11
Cross Module Analysis I/O
12
Input Files
12
Output Files
12
5 | Metrics
13
Metrics Overview
13
Metric Thresholds
13
Threshold Order
14
Function-Based Metrics
14
Class-Based Metrics
14
Page 4


---
*Page 4*

Project-Based Metrics
15
A | RCMA Messages
17
B | RCMA messages not applicable to C language
21
C | Program Return Codes
23
D | Configuration Options
24
-prodoption class::member_encapsulation_ratio
24
-prodoption close_name::any_case
24
-prodoption close_name::ignore
24
-prodoption close_name::sig_char
25
-prodoption close_name::sig_extern_char
25
-prodoption close_name::similar
26
-crossmoduleanalysisfile,-cmaf
27
-echo,-e
27
-forgetall,-forget,-f
27
-prodoption init::entry
28
-prodoption init::functions
28
-list
28
-nomsg,-no,-n
29
-only,-o
29
-outputpath,-op
29
-prodoption pal2::keep_ixx
30
-prodoption pal2::log
30
-prodoption pal2::threads
30
-prodoption,-paloption,-qacppoption,-qo,-po
31
-prodoption qax::limit
31
-quiet,-q
31
-quietextended,-qx
32
-remark,-rem
32
-settings,-set
33
-threshold,-thresh
33
-url
33
-version,-ver,-v
33
-via
34
-virtualmemorylimit,-vml
34
Page 5


---
*Page 5*
