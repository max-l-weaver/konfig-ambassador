import os
import sys
import logging

import yaml
import argparse

from kubernetes import client, config
from kubernetes.config import ConfigException
from kubernetes.client.rest import ApiException

LOGGER = logging.getLogger(__name__)


def _kubernetes_client(env='dev', kube_config=''):
    """Generates kubernetes/openshift session.
    Designed so it can either take a config from a specified path,
    the ./kube dir or from the user's .kube/config
    """

    _dir = os.path.dirname(os.path.realpath(__name__))
    config_file = "kube-%s.config" % ('prod' if env != 'dev' else 'dev')

    if not kube_config:
        kube_config = os.path.join(_dir, 'kube', config_file)
        if not os.path.exists(kube_config):
            kube_config = os.path.join(os.path.expanduser("~"),
                                       '.kube',
                                       'config')
    else:
        kube_config = os.path.expanduser(kube_config)

    try:
        config.load_kube_config(kube_config)
    except (ConfigException, FileNotFoundError) as e:
        LOGGER.error("Error loading Kube config file: %s", e)
    else:
        return client.CoreV1Api()

def _return_service_annotations(kubernetes_client, namespace='', service_name=''):

    try:
        LOGGER.info("retrieving %s details from %s", service_name, namespace)
        print(namespace, service_name)
        service = kubernetes_client.read_namespaced_service(
            namespace=namespace,
            name=service_name
        )
    except ApiException as error:
        LOGGER.error("""Error getting service annotations for %s
check you're logged into the right cluster for %s. Error number is %s""",
        service_name, namespace, error)

    if service is not None:
        return service.metadata.annotations
    else:
        LOGGER.error("""No service information found for %s on %s.
Please ensure the service exists and the service_name/namespace is correct""",
service_name, namespace)
        return service

def _load_yaml(yaml_file=''):

    if not yaml_file:
        LOGGER.error("No yaml file provided - exiting!")
        sys.exit(1)

    if not os.path.exists(yaml_file):
        LOGGER.critical("Yaml file %s doesn't exist, please check and try again",
        yaml_file)
        sys.exit(1)

    try:
        with open(yaml_file, 'r') as yf:
            loaded_yaml = yaml.load(yf)
    except yaml.scanner.ScannerError as e:
        LOGGER.critical("""Error loading yaml file. Is this formatted correctly?
Error is %s. File loaded is %s""", e, yaml_file)

    try:
        LOGGER.debug("testing config file is legit")
        loaded_yaml['platform']['services']
        loaded_yaml['platform']['global']
        loaded_yaml['namespace']
    except KeyError:
        LOGGER.error("""unable to return config file.
Please check it's configured correctly. Please see README for more details.
Exiting as can't go any further""")
        sys.exit(1)

    return loaded_yaml

def _convert_annotations(raw_annotations={}):

    annotations = []

    if not raw_annotations:
        LOGGER.error("no annotations provided - exiting")
        sys.exit(1)

    for k, v in raw_annotations.items():
        if isinstance(v, dict):
            if k == "add_response_headers":
                LOGGER.debug("response headers found - adding")
                annotations.append(f"{k}:\n")
                for key, value in v.items():
                    annotations.append("  {key}: \"{value}\"\n".format(
                        key=key,
                        value=value
                    ))
        else:
            annotations.append(f"{k}: {v}\n")

    return annotations

def _merge_annotations(existing_annotations=[], new_annotations=[]):
    # existing_annotations = existing_annotations.split('\n')
    LOGGER.debug("merging annotations")
    new_annotations = new_annotations

    for annotation in new_annotations:
        existing_annotations.append(annotation)

    try:
        LOGGER.debug("removing any empty elements from annotations")
        existing_annotations.remove('') # Remove any empty elements
    except ValueError:
        LOGGER.debug("no empty elements found - skipping")
        pass

    LOGGER.debug("annotations merged. Merged body is %s", existing_annotations)
    return existing_annotations

def update_annotations(kubernetes_session, annotations, namespace='', service_name='', dry_run=False):

    # Apparently you have to pass a string to dry run :wat:
    if dry_run:
        dry_run = 'All'
    else:
        dry_run = ''

    body = client.V1Service
    metadata_object = client.V1ObjectMeta

    metadata_object = metadata_object(
        annotations={"getambassador.io/config": ''.join(annotations)}
    )
    body = body(metadata=metadata_object)
    LOGGER.debug("preparing body for updating. %s", body)

    try:
        LOGGER.info("Patching service %s on %s", service_name, namespace)
        patched_service = kubernetes_session.patch_namespaced_service(
            namespace=namespace,
            name=service_name,
            body=body,
            dry_run=dry_run
        )
    except ApiException as e:
        LOGGER.error("Error getting service %s. Error is %s", service_name, e)
        return
    else:
        return patched_service

def argument_parser():
    args = argparse.ArgumentParser()
    args.add_argument("--config-file", help="""The yaml file containing
annotations settings. If ommited then they will need to be parsed as json""")
    args.add_argument("--dry-run", action='store_false', help="""The yaml file containing
annotations settings. If ommited then they will need to be parsed as json""")

    return args.parse_args()

def main():

    LOGGER.debug("loading config file")
    loaded_file = _load_yaml(argument_parser().config_file)

    namespace = loaded_file['namespace']
    LOGGER.debug("found namespace: %s", namespace)

    LOGGER.info("Updating annotations for %s", namespace)

    LOGGER.debug("Creating kubernetes session")
    env = namespace.split('-')
    if len(env) <= 1:
        LOGGER.error("""Incorrect namespace format provided for namespace %s.
Namespace should be in the format {client}-{env}""", namespace)
        sys.exit(1)
    env = env[-1]
    session = _kubernetes_client(env)
    globes = []

    try:
        globes = loaded_file['global']
    except KeyError:
        LOGGER.info("no globals set - skipping")

    if globes:
        globes = _convert_annotations(globes)

    for k, v in loaded_file['platform']['services'].items():
        converted = _convert_annotations(v)
        merged = _merge_annotations(converted, globes)
        updated = update_annotations(
            session,
            annotations=merged,
            namespace=namespace,
            service_name=k,
            dry_run=argument_parser().dry_run
        )


if __name__ == '__main__':
    main()
