"""Bounded dependency scheduling shared by job and workflow execution."""

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from ..domain.execution.model import Status


def schedule(nodes, needs, run, skip, cancel, max_workers):
    pending = dict(nodes)
    completed = {}
    running = {}
    with ThreadPoolExecutor(
        max_workers=max_workers, thread_name_prefix="ptk-graph"
    ) as pool:
        try:
            while pending or running:
                for future in list(running):
                    if future.done():
                        completed[running.pop(future)] = future.result()
                for name, node in list(pending.items()):
                    if cancel.is_set():
                        completed[name] = skip(node, Status.CANCELLED, "cancelled")
                    elif not all(parent in completed for parent in needs[name]):
                        continue
                    else:
                        blocked = [
                            f"{parent} ({completed[parent].status.value})"
                            for parent in needs[name]
                            if completed[parent].status != Status.PASSED
                            and not completed[parent].allowed_failure
                        ]
                        if blocked:
                            completed[name] = skip(
                                node,
                                Status.SKIPPED,
                                "blocked by needs: " + ", ".join(blocked),
                            )
                        elif len(running) < max_workers:
                            running[pool.submit(run, node)] = name
                        else:
                            continue
                    del pending[name]
                if running:
                    wait(running, timeout=0.1, return_when=FIRST_COMPLETED)
        except BaseException:
            cancel.set()
            raise
    return [completed[name] for name in nodes]
