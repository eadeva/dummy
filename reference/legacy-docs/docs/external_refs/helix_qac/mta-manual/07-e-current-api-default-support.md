# E |  Current API Default Support

E | Current API Default Support
This list is automatically generated.
API: pthreads
Thread functions
pthread_create
pthread_join
Mutex functions
pthread_mutex_init
pthread_mutex_destroy
pthread_mutex_unlock
pthread_mutex_lock
pthread_mutex_trylock
pthread_mutex_timedlock
Condition variable functions
pthread_cond_init
API: Windows
Thread functions
CreateThread
_beginthread
_beginthreadex
WaitForSingleObject
WaitForSingleObjectEx
SignalObjectAndWait
Mutex functions
CreateMutexA
CreateMutexExA
CreateMutexW
CreateMutexExW
OpenMutexA
OpenMutexW
CloseHandle
ReleaseMutex
WaitForSingleObject
WaitForSingleObjectEx
SignalObjectAndWait
InitializeCriticalSection
InitializeCriticalSectionAndSpinCount
InitializeCriticalEx
DeleteCriticalSection
EnterCriticalSection
LeaveCriticalSection
SleepConditionVariableCS
TryEnterCriticalSection
InitializeSRWLock
AcquireSRWLockExclusive
Page 23


---
*Page 23*

AcquireSRWLockShared
ReleaseSRWLockExclusive
ReleaseSRWLockShared
SleepConditionVariableSRW
TryAcquireSRWLockExclusive
TryAcquireSRWLockShared
Condition variable functions
InitializeConditionVariable
API: C11
Thread functions
thrd_create
thrd_join
Mutex functions
mtx_init
mtx_destroy
mtx_lock
mtx_unlock
mtx_trylock
mtx_timedlock
Condition variable functions
cnd_init
API: C++11
Thread functions
std::thread::@constructor
std::thread::join
Mutex functions
std::mutex::lock
std::mutex::unlock
std::mutex::try_lock
std::unique_lock::lock
std::unique_lock::unlock
std::unique_lock::try_lock
std::unique_lock::try_lock_for
std::unique_lock::try_lock_until
Condition variable functions
std::condition_variable::@constructor
std::condition_variable_any::@constructor
Page 24


---
*Page 24*
