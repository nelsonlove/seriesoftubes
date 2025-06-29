"""Celery configuration"""

import os

# Broker settings - using Redis
broker_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
result_backend = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Task settings
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']
timezone = 'UTC'
enable_utc = True

# Worker settings
worker_prefetch_multiplier = 1  # Prevent workers from prefetching too many tasks
worker_max_tasks_per_child = 50  # Restart workers after 50 tasks to prevent memory leaks

# Task execution settings
task_acks_late = True  # Tasks are acknowledged after they complete
task_reject_on_worker_lost = True  # Reject tasks if worker dies

# Task time limits
task_soft_time_limit = 1800  # 30 minutes soft limit (raises exception)
task_time_limit = 3600  # 60 minutes hard limit (kills task)

# Result backend settings
result_expires = 3600  # Results expire after 1 hour

# Routing - could route different node types to different queues
task_routes = {
    'seriesoftubes.execute_workflow': {'queue': 'workflows'},
    'seriesoftubes.execute_node': {'queue': 'nodes'},
}

# Queue configuration
task_default_queue = 'workflows'
task_queues = {
    'workflows': {
        'exchange': 'workflows',
        'routing_key': 'workflow.execute',
    },
    'nodes': {
        'exchange': 'nodes', 
        'routing_key': 'node.execute',
    },
}