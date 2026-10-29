# D | Glossary

D | Glossary
Atomic
An atomic object or operation is one which is fundamentally indivisible and therefore needs no protection from concurrent
access.
Atomicity ultimately depends on support from the underlying hardware, but is usually abstracted by the operating system
or C/C++ library. We do not describe it in further detail for MTA.
Colocated objects
Colocated objects are those which appear to be distinct entities in the source code, but which are physically part of the
same hardware resource and cannot be accessed in a truly separate fashion. When one of a colocated pair is modified
on one thread, it may temporarily affect the value of the other as seen on another thread.
The C and C++ language standards make certain guarantees of independence, but where those are not applicable, data
races may occur.
There are two main types of colocated objects:
n Union members.
n Adjacent struct members that are packed into a single machine-addressable unit. The most common example is
with bit fields, although in some architectures, anything smaller than 'int' may not be accessible in isolation.
Concurrent threads
Threads that can run in parallel during the execution of a program. Because execution timing and thread blocking
behaviours are often not deterministic or predictable, design errors may not cause problems during testing and only
show up on live workloads. Refer to Thread for more information.
Note:
Thread join (that is, waiting for another thread function to complete its execution and return) is
synchronous/blocking, unlike thread creation.
Condition variable
A condition variable is a synchronisation primitive which allows one or more threads to wait until a particular condition
occurs. They must be used in conjunction with a Mutex, and while it is legitimate to use more than one condition variable
with the same mutex, it is normally an error to use a single variable with different mutexes.
See Current API Default Support for the condition variable APIs currently supported.
Condition variable wait inconsistency
Waiting on a condition variable with different Mutex in Concurrent threads.
Critical section
A region of code that must only be executed by a single thread at a time.
Page 18


---
*Page 18*

To ensure that this is the case, critical sections are protected by synchronisation objects called Mutex.
Data race
A write to a Shared object in one Thread coupled with a read or write to the same object in a Concurrent threads and not
protected by a Mutex or performed using Atomic functions.
Data races can cause hard-to-diagnose failures which would appear to be 'impossible' when looking at any one piece of
code in isolation.
Deadlock
Deadlock typically occurs when two threads each own a resource the other needs, so neither can proceed.
More generally, it occurs if there are any closed cycles in the Lock graph with Concurrent threads.
Deadlock can be avoided by ensuring that the lock graph is acyclic, which is most simply achieved by enforcing a
standard order in which any multiple locks are acquired. This is a stronger condition than strictly necessary, but it is
usually the simplest way to ensure a robust design.
Inter thread analysis
The MTA component processes thread summaries for the whole project and provides the following checks:
Check
messages
Data race for the same Shared object
1765, 1766, 1770, 1771
Data race for adjacent Shared object
1774, 1775
Deadlock
1767, 1768
Violating a Lock hierarchy
1772, 1773
Condition variable wait inconsistency
1769
Thread not joined or detached exactly once
1776, 1777
Condition variable signalled and used with multiple wait operations
1778, 1779
Misuse of Thread Local Storage allocation
1780-1784
Due to the nature of the Concurrent threads detection and static analysis in general, these analysis checks provide an
over approximation, and will detect violations even under obscure timing conditions and program input.
Intra thread analysis
Each Thread detected during dataflow analysis is checked for the following issues:
Check
messages
Using a Mutex which has not been initialised
4936, 4937
Page 19


---
*Page 19*

Check
messages
Initialising a Mutex which has already been initialised
4931, 4932
Attempt to destroy a Mutex which is still locked
4961, 4962
Attempt to destroy a Mutex which has not been created by the current Thread
4971, 4972
Attempt to unlock a Mutex which has not been locked by the current Thread
4981, 4982
Attempt to lock a non-recursiveMutex which is already locked
4986, 4987
Mutex is still locked at Thread exit
4946, 4947
Beware of race conditions when using fork and file descriptors
4951, 4952
Performing a blocking action in a Critical section
4966, 4967
Call to a non-reentrant function outside of a Critical section
4976, 4977
Using an invalid Thread identifier
4995-4998
In addition, thread summaries are written out during this stage of analysis.
To minimize false negatives for the above checks, and write out the most accurate summaries, the following analysis
options can be specified:
-po df::inter
-po df::cma
Please refer to the Helix QAC for C or Helix QAC for C++ user manual for detailed usage of these options.
Lock graph
A directed graph with Mutex as nodes and an edge for every locking operation in a Thread from a mutex already held to a
mutex being acquired.
Lock hierarchy
A partial order of mutexes (nodes in a Lock graph). A lock graph only consisting of edges x→y, such that x<y, is
guaranteed not to have cycles (no y→x edge that closes a cycle), which prevents a necessary condition for Deadlock.
x→x edges are detected at Inter thread analysis.
All edges are considered, regardless of the Thread the edge originates from, as a lock hierarchy violation in a group of
Concurrent threads is equivalent to deadlock.
Main function
One of: main, wmain, WinMain, DllMain, wWinMain, wDllMain, or _prqa_main.
Note:
A custom main function can be specified (perhaps in a force include file) as:
Page 20


---
*Page 20*

int _prqa_main (void)
{
return mymain ();
Mutex
An object used to ensure that a Critical section can only be executed by one thread at a time, or to protect a Shared
object and ensure that all Concurrent threads see a consistent value.
We use the generic term 'mutex' within MTA in all cases, although specific programming environments may use different
terms.
For example, in the Win32 API, there are different types of objects, known as 'Critical Section Objects', 'Mutexes' and
'Slim Reader/Writer Locks', all of which perform the same basic protection function, but in different ways with different
costs and benefits. Nevertheless, they are all just mutexes within MTA.
Note:
We do not presently model recursive mutexes or semaphores.
A recursive mutex is one which can be acquired more than once by the same thread, so the thread will
not block itself if it attempts to acquire a mutex it already owns. The mutex must be released once for
each nested acquisition.
A semaphore is similar to a mutex but can be acquired by more than one thread simultaneously, up to
some limit after which further requests will block.
See Current API Default Support for the mutex APIs currently supported.
Shared object
In the MTA context, this refers to any Atomic object which can be accessed by more than one Thread.
In C/C++ terms, this means any object with static storage duration which is visible within a Thread Function, or functions
that it calls, together with objects accessible via a pointer or reference passed from the thread creator as an argument to
the thread function.
In most operating systems and C bindings, a native thread function receives a single generic pointer/int parameter. MTA
notes the actual parameter passed in each specific thread creation instance, although C++ libraries (including the
Standard Library) may provide a multi-parameter interface.
Thread
A thread is an independent unit of execution which may proceed in parallel with other threads. The code that it executes
is a Thread Function and traditionally, a C/C++ program contained a single thread running a single function called main().
Multithreaded programs can contain any number of additional threads and thread functions. Each function may be
executed by its own unique thread or by several, and threads may run Concurrent threads, sequentially or a mixture of
the two.
See Current API Default Support for the thread APIs currently supported.
Page 21


---
*Page 21*

Thread Function
The code that a Thread executes. Thread creation APIs take such a function as a parameter, and the program's Main
function is a thread function by definition.
Functions inlined by Dataflow (see -po df::inter Dataflow option) are not themselves thread functions, but are analyzed as
a consequence of inlining.
See Current API Default Support for the thread creation APIs currently supported.
Thread summary
A record of the following operations performed by a Thread :
n read or write of a Shared object
n read or write of a Colocated objects
n Mutex lock/unlock.
n thread creation or thread join.
n Condition variable wait.
To facilitate accurate Inter thread analysis, the following information is recorded for each event:
n known Concurrent threads
n known locked Mutex.
Page 22


---
*Page 22*
