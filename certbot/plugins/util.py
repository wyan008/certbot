"""Plugin utilities."""
import logging
import socket

import zope.component

from certbot import interfaces

try:
    import psutil
    USE_PSUTIL = True
except ImportError:
    USE_PSUTIL = False

logger = logging.getLogger(__name__)

RENEWER_EXTRA_MSG = (
    " For automated renewal, you may want to use a script that stops"
    " and starts your webserver. You can find an example at"
    " https://letsencrypt.org/howitworks/#writing-your-own-renewal-script"
    ". Alternatively you can use the webroot plugin to renew without"
    " needing to stop and start your webserver.")


def already_listening(port, renewer=False):
    """Check if a process is already listening on the port.

    If so, also tell the user via a display notification.

    .. warning::
        On some operating systems, this function can only usefully be
        run as root.

    :param int port: The TCP port in question.
    :returns: True or False.

    """

    if USE_PSUTIL:
        return already_listening_psutil(port, renewer=renewer)
    else:
        logger.debug("Psutil not found, using simple socket check.")
        return already_listening_socket(port, renewer=renewer)


def already_listening_socket(port, renewer=False):
    """Simple socket based check to find out if port is already in use

    :param int port: The TCP port in question.
    :returns: True or False
    """

    try:
        testsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        try:
            testsocket.bind(("", port))
        except socket.error:
            display = zope.component.getUtility(interfaces.IDisplay)
            extra = ""
            if renewer:
                extra = RENEWER_EXTRA_MSG
            display.notification(
                "Port {0} is already in use by another process. This will "
                "prevent us from binding to that port. Please stop the "
                "process that is populating the port in question and try "
                "again. {1}".format(port, extra), height=13)
            return True
        finally:
            testsocket.close()
    except socket.error:
        pass
    return False


def already_listening_psutil(port, renewer=False):
    """Psutil variant of the open port check

    :param int port: The TCP port in question.
    :returns: True or False.

    """
    try:
        net_connections = psutil.net_connections()
    except psutil.AccessDenied as error:
        logger.info("Access denied when trying to list network "
                    "connections: %s. Are you root?", error)
        # this function is just a pre-check that often causes false
        # positives and problems in testing (c.f. #680 on Mac, #255
        # generally); we will fail later in bind() anyway
        return False

    listeners = [conn.pid for conn in net_connections
                 if conn.status == 'LISTEN' and
                 conn.type == socket.SOCK_STREAM and
                 conn.laddr[1] == port]
    try:
        if listeners and listeners[0] is not None:
            # conn.pid may be None if the current process doesn't have
            # permission to identify the listening process!  Additionally,
            # listeners may have more than one element if separate
            # sockets have bound the same port on separate interfaces.
            # We currently only have UI to notify the user about one
            # of them at a time.
            pid = listeners[0]
            name = psutil.Process(pid).name()
            display = zope.component.getUtility(interfaces.IDisplay)
            extra = ""
            if renewer:
                extra = RENEWER_EXTRA_MSG
            display.notification(
                "The program {0} (process ID {1}) is already listening "
                "on TCP port {2}. This will prevent us from binding to "
                "that port. Please stop the {0} program temporarily "
                "and then try again.{3}".format(name, pid, port, extra),
                height=13)
            return True
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        # Perhaps the result of a race where the process could have
        # exited or relinquished the port (NoSuchProcess), or the result
        # of an OS policy where we're not allowed to look up the process
        # name (AccessDenied).
        pass
    return False
