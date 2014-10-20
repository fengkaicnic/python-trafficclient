try:
    import trafficclient.cient
    Client = trafficclient.client.Client
except ImportError:
    import warnings
    warnings.warn('could not import trafficclient', ImportWarning)
    
import trafficclient.versions

__version__ = trafficclient.version.version_info.deffered_version_string()
    