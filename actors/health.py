# Ensures that:
# 1. all worker containers in the database are still responsive; workers that have stopped
#    responding are shutdown and removed from the database.
# 2. Enforce ttl for idle workers.
#
# In the future, this module will also implement:
# 3. all actors with stateless=true have a number of workers proportional to the messages in the queue.

# Execute from a container on a schedule as follows:
# docker run -it --rm -v /var/run/docker.sock:/var/run/docker.sock jstubbs/abaco_core python3 -u /actors/health.py

import time

import channelpy

import codes
from config import Config
from docker_utils import rm_container, DockerError, container_running, run_container_with_docker
from models import Actor, delete_worker, get_workers
from channels import CommandChannel, WorkerChannel
from stores import actors_store
from worker import shutdown_worker

def get_actor_ids():
    """Returns the list of actor ids currently registered."""
    return [db_id for db_id, _ in actors_store.items()]

def check_workers(actor_id, ttl):
    """Check health of all workers for an actor."""
    print("Checking health for actors: {}".format(actor_id))
    workers = get_workers(actor_id)
    print("workers: {}".format(workers))
    for worker in workers:
        # ignore workers on different hosts
        if not Config.get('spawner', 'host_id') == worker['host_id']:
            continue
        # first check if worker is responsive; if not, will need to manually kill
        print("Checking health for worker: {}".format(worker))
        ch = WorkerChannel(name=worker['ch_name'])
        try:
            print("Issuing status check to channel: {}".format(worker['ch_name']))
            result = ch.put_sync('status', timeout=5)
        except channelpy.exceptions.ChannelTimeoutException:
            print("Worker did not respond, removing container and deleting worker.")
            try:
                rm_container(worker['cid'])
            except DockerError:
                pass
            delete_worker(actor_id, worker['ch_name'])
            continue
        if not result == 'ok':
            print("Worker responded unexpectedly: {}, deleting worker.".format(result))
            rm_container(worker['cid'])
            delete_worker(actor_id, worker['ch_name'])
        else:
            print("Worker ok.")
        # now check if the worker has been idle beyond the ttl:
        if ttl < 0:
            # ttl < 0 means infinite life
            print("Infinite ttl configured; leaving worker")
            return
        if worker['status'] == codes.READY and \
            worker['last_execution'] + ttl < time.time():
            # shutdown worker
            print("Shutting down worker beyond ttl.")
            shutdown_worker(worker['ch_name'])
        else:
            print("Worker still has life.")

def manage_workers(actor_id):
    """Scale workers for an actor if based on message queue size and policy."""
    print("Entering manage_workers for {}".format(actor_id))
    try:
        actor = Actor.from_db(actors_store[actor_id])
    except KeyError:
        print("Did not find actor; returning.")
        return
    workers = get_workers(actor_id)
    #TODO - implement policy

def main():
    print("Running abaco health checks. Now: {}".format(time.time()))
    ttl = Config.get('workers', 'worker_ttl')
    if not container_running(image='jstubbs/abaco_core', name='abaco_spawner*'):
        print("No spawners running! Launching new spawner..")
        command = 'python3 -u /actors/spawner.py'
        run_container_with_docker('jstubbs/abaco_core', command, name='abaco_spawner_0')
    try:
        ttl = int(ttl)
    except Exception:
        ttl = -1
    ids = get_actor_ids()
    print("Found {} actor(s). Now checking status.".format(len(ids)))
    for id in ids:
        check_workers(id, ttl)
        # manage_workers(id)


if __name__ == '__main__':
    main()