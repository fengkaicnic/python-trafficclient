try:
    import trafficclient.cient
    Client = trafficclient.client.Client
except ImportError:
    import warnings
    warnings.warn('could not import trafficclient', ImportWarning)
    
import trafficclient.version

__version__ = trafficclient.version.version_info.defered_version_string()
    