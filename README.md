# Kongfig for Ambassador

Like the ambassador himself, who hands out Forrero Rochers to all his distinguished guests, ambassador api hands out
whatever the api equivilent of hazelnut filled chocolate balls are to Openshift.

Unfortunately there isn't an easy way to update the annotations without manually editing. `Kongfig-for-ambassador` is an
attempt to resolve this by offering kongfig style functionality to ambassador.

## Config file

In order to avoid needless duplication the config file has been arranged by global settings and service specific settings.

Have a setting in both global and under the service will *not* overwrite the global or vice-versa. At the moment this functionality
is unavailable so it will just create duplicate values.

The config file must be in yaml format and contain the following keys:

```
namespace: foo-bar-dev
platform:
  global:
    # global settings
  services:
    service_name:
      # service info
```

## Command

```
$ python3.7 -m venv venv
$ . venv/bin/activate
$(venv) pip install -r requirements.txt
$(venv) ./main.py --config /path/to/config/file.yaml
```

You can also pass in the `--debug` flag if you wish to see a more verbose output

## What it does

Ambassador service settings are configured as an unstructured key/value object within the service object and are difficult
to manipulate due to the fact that they're formatted as one long string. What this program does is replace the annotations
entirely, meaning every time it's run on a service that service will have it's annotations replaced and will be restarted.
