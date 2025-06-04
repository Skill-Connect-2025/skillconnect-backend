# core/constants.py
JOB_STATUS_CHOICES = (
    ('posted', 'Posted'),           # Initial state when job is created
    ('open', 'Open'),              # Job is available for applications/requests
    ('in_progress', 'In Progress'), # Job has been assigned and is being worked on
    ('completed', 'Completed'),     # Job is done but pending feedback
    ('closed', 'Closed'),          # Job is fully completed with feedback
    ('cancelled', 'Cancelled'),    # Job was cancelled
)

JOB_APPLICATION_STATUS_CHOICES = (
    ('pending', 'Pending'),      # Worker applied, awaiting client response
    ('accepted', 'Accepted'),    # Client accepted worker's application
    ('rejected', 'Rejected'),    # Client rejected worker's application
)

JOB_REQUEST_STATUS_CHOICES = (
    ('pending', 'Pending'),      # Client sent request, awaiting worker response
    ('accepted', 'Accepted'),    # Worker accepted client's request
    ('rejected', 'Rejected'),    # Worker rejected client's request
)

PAYMENT_METHOD_CHOICES = (
    ('cash', 'Cash'),
    ('chapa', 'Chapa'),
)