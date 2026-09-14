# Gunicorn configuration file
import multiprocessing
import os
import resource
import tempfile

# Spool uploads to the large data volume, not to / (30G, and near full).
# Werkzeug buffers each incoming file to a temp file before the view sees it,
# so a large video upload would otherwise land on the root filesystem.
UPLOAD_TMPDIR = "/mnt/volume-nyc1-01/tmp"
if os.path.isdir(UPLOAD_TMPDIR) and os.access(UPLOAD_TMPDIR, os.W_OK):
    os.environ["TMPDIR"] = UPLOAD_TMPDIR
    tempfile.tempdir = UPLOAD_TMPDIR

# Raise the file-descriptor ceiling for the arbiter and every worker it forks.
# The previous 1024 soft limit was reached by leaked sockets, after which
# accept() failed with EMFILE and the whole site stopped answering.
_soft, _hard = resource.getrlimit(resource.RLIMIT_NOFILE)
resource.setrlimit(resource.RLIMIT_NOFILE, (min(65536, _hard), _hard))

# Server socket
bind = "0.0.0.0:8500"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2
worker_class = "gthread"  # Use threads
threads = 2
worker_connections = 1000
timeout = 300  # 5 minutes
graceful_timeout = 300
keepalive = 2

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Process naming
proc_name = "kongaloosh"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL
keyfile = None
certfile = None
