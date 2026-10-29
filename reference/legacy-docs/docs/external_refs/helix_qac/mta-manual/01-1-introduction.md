# 1 | Introduction

1 | Introduction
Most software today runs on multi-core processors. If a program wants to utilize the available computing capability fully, it
needs to arrange that its various tasks run in parallel. This is known as multi-threading. Multi-threading can speed up
programs, but the individual Thread will need to communicate with each other and synchronize their work, so this can
also lead to concurrency issues, such asDeadlock and Data race .
In addition, there are various synchronization APIs available—which you can find in Current API Default Support—with
varying degree of care that must be taken to use them correctly. Majority of multi-threading issues are classed as
undefined behaviour, so have direct security implications, and commonly feature in security focused coding standards.
Multi-Threading Analysis (MTA) Overview
Multi-Threading Analysis is carried out by Helix QAC in 2 stages:
n Intra-thread analysis
n Inter-thread analysis
Inter-thread analysis
Analysis of all threads in a program (by means of processing thread summaries) carried out by the MTA component, for
issues that only arise when multiple threads are running concurrently. Refer to the following topics for more information:
n Thread
n Thread summary
n Concurrent threads
Some design and logic flaws can be detected in isolation, such as locking a mutex and not unlocking it, which is the
purpose of intra-thread analysis. Refer to Intra-thread analysis for more information.
The messages that can be emitted by inter-thread analysis are listed in Inter thread analysis.
Intra-thread analysis
Analysis of a thread function in isolation, to detect errors such as failure to release a lock, or calling a blocking function
while still holding a lock. Refer to Thread Function for more information.
These are general design or logic flaws which do not depend on the interrelationship between threads.
The inter-thread analysis stage checks for issues that may arise when functions are executed concurrently. Refer to
Inter-thread analysis and Concurrent threads for more information.
The messages that can be emitted by intra-thread analysis are listed in Intra thread analysis
Running MTA
MTA is installed as part of Helix QAC version 2019.1 or later.
See ‘Activating Dataflow Analysis’ in the Helix QAC for C or Helix QAC for C++ component manual to enable intra-thread
analysis. Refer to Intra-thread analysis for more information.
Inter-thread analysis can be applied to your project via the Analysis Toolchain, under the Analysis tab in Helix QAC
Project Properties. Refer to Inter-thread analysis for more information.
Page 6


---
*Page 6*
