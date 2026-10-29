# Important Notice

Important Notice
Change of Company Ownership
Programming Research Ltd., also known as “PRQA”, became a wholly owned subsidiary of Perforce Software Inc., also
known as “Perforce”, in May 2018.
Disclaimer of Warranty
This document should only be used in conjunction with MTA.
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
Multi-Threading Analysis (MTA) Overview
6
Inter-thread analysis
6
Intra-thread analysis
6
Running MTA
6
2 | MTA Configuration
7
Message Suppression
7
Comment-Based Suppressions
7
A | MTA Messages
8
B | Program Return Codes
10
C | Configuration Options
11
-crossmoduleanalysisfile,-cmaf
11
-echo,-e
11
-forgetall,-forget,-f
11
-list
12
-nomsg,-no,-n
12
-only,-o
12
-outputpath,-op
13
-prodoption,-paloption,-qacppoption,-qo,-po
13
-prodoption qax::limit
13
-quiet,-q
14
-quietextended,-qx
15
-remark,-rem
15
-settings,-set
15
-url
16
-version,-ver,-v
16
-via
16
Page 4


---
*Page 4*

-virtualmemorylimit,-vml
16
D | Glossary
18
Atomic
18
Colocated objects
18
Concurrent threads
18
Condition variable
18
Condition variable wait inconsistency
18
Critical section
18
Data race
19
Deadlock
19
Inter thread analysis
19
Intra thread analysis
19
Lock graph
20
Lock hierarchy
20
Main function
20
Mutex
21
Shared object
21
Thread
21
Thread Function
22
Thread summary
22
E | Current API Default Support
23
Page 5


---
*Page 5*
