"""
Task runners
============

The task runners are responsible for running all the tasks (either in series
or in parallel). There's only one task runner per activity. The base is
"""

from concurrent import futures
from concurrent.futures import ThreadPoolExecutor


DEFAULT_TASK_TIMEOUT = 600  # 10 minutes.


class NoRunnerRequirementsFound(Exception):
    pass


class BaseRunner():

    def __init__(self, *args):
        self.tasks = args

    @property
    def timeout(self):
        """Calculate and return the timeout for an activity.

        The calculation of the timeout is pessimistic: it takes the worse case
        scenario (even for asynchronous task lists, it supposes there is only
        one thread completed at a time.)

        Return:
            str: The timeout (boto requires the timeout to be a string and not
                a regular number.)
        """

        timeout = 0

        for task in self.tasks:
            task_timeout = DEFAULT_TASK_TIMEOUT
            task_details = getattr(task, '__garcon__', None)

            if task_details:
                task_timeout = task_details.get(
                    'timeout', DEFAULT_TASK_TIMEOUT)

            timeout = timeout + task_timeout

        return str(timeout)

    @property
    def requirements(self):
        """Find all the requirements from the list of tasks and return it.

        If a task does not use the `task.decorate`, no assumptions can be made
        on which values from the context will be used, and it will raise an
        exception.

        Raise:
            NoRequirementFound: The exception when no requirements have been
                mentioned in at least one or more tasks.

        Return:
            set: the list of the required values from the context.
        """

        requirements = []

        for task in self.tasks:
            task_details = getattr(task, '__garcon__', None)
            if task_details:
                requirements += task_details.get('requirements', [])
            else:
                raise NoRunnerRequirementsFound()

        return set(requirements)

    def execute(self, activity, context):
        """Execution of the tasks.
        """

        raise NotImplementedError


class Sync(BaseRunner):

    def execute(self, activity, context):
        result = dict()
        for task in self.tasks:
            task_context = dict(list(result.items()) + list(context.items()))
            resp = task(task_context, activity=activity)
            result.update(resp or dict())
        return result


class Async(BaseRunner):

    def __init__(self, *args, **kwargs):
        self.tasks = args
        self.max_workers = kwargs.get('max_workers', 3)

    def execute(self, activity, context):
        result = dict()
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            tasks = []
            for task in self.tasks:
                tasks.append(executor.submit(task, context, activity=activity))

            for future in futures.as_completed(tasks):
                data = future.result()
                result.update(data or {})
        return result