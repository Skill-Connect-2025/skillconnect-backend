# SkillConnect Admin API Documentation

## Overview

**Base URL**: `https://api.skillconnect.wisewaytech.com`

## Authentication
All admin API endpoints require authentication using a token. Only users with admin privileges can access these endpoints.

### Token Management
The admin token is required for all management API endpoints. The token should be included in the `Authorization` header of every request:

```http
Authorization: Token a68cb591bd3e12365facfbe16448e90c1016d83c
```

**Important Notes:**
- The token is valid for 24 hours
- Store the token securely in your frontend application
- Use environment variables to store the token
- Never expose the token in client-side code
- Implement token refresh mechanism
- Handle token expiration gracefully

### Login
```http
POST /users/auth/login/
Content-Type: application/json

{
    "identifier": "email@example.com", // or phone number
    "password": "your_password"
}
```

**Response (200 OK)**:
```json
{
    "token": "your_auth_token",
    "user": {
        "id": 1,
        "username": "admin",
        "first_name": "Admin",
        "last_name": "User",
        "role": "admin",
        "email": "email@example.com",
        "phone_number": "+251911123456"
    }
}
```

**Important Notes**:
- Store the token securely (preferably in HttpOnly cookies)
- Include token in all requests: `Authorization: Token your_auth_token`
- Include CSRF token for POST/PUT/DELETE: `X-CSRFToken: your_csrf_token`

## Admin API Endpoints

### User Management

#### 1. List Users
```http
GET /api/management/users/search/
```
Lists all users with optional filtering.

**Query Parameters:**
- `query` (string): Search by username, email, phone, or name
- `role` (string): Filter by role ('client' or 'worker')
- `status` (string): Filter by status ('active' or 'suspended')
- `date_from` (string): Filter by join date (YYYY-MM-DD)
- `date_to` (string): Filter by join date (YYYY-MM-DD)

**Response (200 OK):**
```json
[
    {
        "id": 1,
        "username": "john.doe",
        "email": "john@example.com",
        "phone_number": "+251911123456",
        "first_name": "John",
        "last_name": "Doe",
        "is_active": true,
        "is_client": true,
        "is_worker": false,
        "rating_stats": {
            "average_rating": 4.5,
            "total_ratings": 10
        }
    }
]
```

#### 2. Get User Details
```http
GET /api/management/users/{user_id}/
```
Get detailed information about a specific user.

**Response (200 OK):**
```json
{
    "id": 1,
    "username": "john.doe",
    "email": "john@example.com",
    "phone_number": "+251911123456",
    "first_name": "John",
    "last_name": "Doe",
    "is_active": true,
    "is_client": true,
    "is_worker": false,
    "rating_stats": {
        "average_rating": 4.5,
        "total_ratings": 10,
        "rating_distribution": {
            "1": 0,
            "2": 1,
            "3": 2,
            "4": 4,
            "5": 3
        }
    }
}
```

#### 3. Update User
```http
PUT /api/management/users/{user_id}/
Content-Type: application/json

{
    "username": "john.doe",
    "email": "john@example.com",
    "phone_number": "+251911123456",
    "first_name": "John",
    "last_name": "Doe"
}
```

#### 4. Suspend/Activate User
```http
POST /api/management/users/{user_id}/suspend/
Content-Type: application/json

{
    "is_active": false,
    "reason": "Violation of terms of service"
}
```

#### 5. Reset User Password
```http
POST /api/management/users/{user_id}/reset-password/
```
Sends a password reset code to the user's email/phone.

#### 6. Bulk User Actions
```http
POST /api/management/users/bulk-action/
Content-Type: application/json

{
    "user_ids": [1, 2, 3],
    "action": "suspend" // or "activate" or "delete"
}
```

### Analytics Dashboard

#### 1. Get Analytics Dashboard
```http
GET /api/management/analytics/dashboard/
```
Get comprehensive system analytics.

**Query Parameters:**
- `period` (string): Time period ('daily', 'weekly', 'monthly')
- `start_date` (string): Start date (YYYY-MM-DD)
- `end_date` (string): End date (YYYY-MM-DD)

**Response (200 OK):**
```json
{
    "user_metrics": {
        "total_users": 1000,
        "active_users": 800,
        "new_users": 50,
        "user_growth_rate": 0.05,
        "user_retention_rate": 0.85
    },
    "job_metrics": {
        "total_jobs": 500,
        "completed_jobs": 300,
        "active_jobs": 150,
        "completion_rate": 0.6,
        "average_job_duration": 48.5
    },
    "financial_metrics": {
        "total_transactions": 300,
        "total_volume": 150000.00,
        "average_transaction": 500.00,
        "payment_method_distribution": {
            "cash": 0.6,
            "chapa": 0.4
        }
    },
    "quality_metrics": {
        "average_rating": 4.2,
        "rating_distribution": {
            "1": 10,
            "2": 20,
            "3": 50,
            "4": 150,
            "5": 200
        },
        "dispute_rate": 0.02,
        "resolution_rate": 0.95
    },
    "trends": {
        "user_growth": [...],
        "job_activity": [...],
        "revenue": [...]
    }
}
```

### Dispute Management

#### 1. List Disputes
```http
GET /api/management/disputes/
```
List all disputes with optional filtering.

**Query Parameters:**
- `status` (string): Filter by status ('pending', 'in_review', 'resolved', 'closed')
- `type` (string): Filter by type ('payment', 'quality', 'behavior', 'other')

**Response (200 OK):**
```json
[
    {
        "id": 1,
        "job": {
            "id": 1,
            "title": "House Cleaning"
        },
        "reported_by": {
            "id": 1,
            "username": "john.doe"
        },
        "reported_user": {
            "id": 2,
            "username": "jane.smith"
        },
        "dispute_type": "payment",
        "description": "Payment not received",
        "status": "pending",
        "created_at": "2024-03-15T10:00:00Z"
    }
]
```

#### 2. Get Dispute Details
```http
GET /api/management/disputes/{id}/
```

#### 3. Resolve Dispute
```http
POST /api/management/disputes/{id}/resolve/
Content-Type: application/json

{
    "resolution": "Payment will be processed within 24 hours"
}
```

#### 4. Close Dispute
```http
POST /api/management/disputes/{id}/close/
```

#### 5. Get Dispute Statistics
```http
GET /api/management/disputes/statistics/
```

**Response (200 OK):**
```json
{
    "total_disputes": 100,
    "disputes_by_status": {
        "pending": 20,
        "in_review": 30,
        "resolved": 40,
        "closed": 10
    },
    "disputes_by_type": {
        "payment": 40,
        "quality": 30,
        "behavior": 20,
        "other": 10
    },
    "average_resolution_time_hours": 24.5
}
```

### Notification Management

#### 1. List Notification Templates
```http
GET /api/management/notifications/templates/
```

#### 2. Create Notification Template
```http
POST /api/management/notifications/templates/
Content-Type: application/json

{
    "name": "Job Assigned",
    "subject": "New Job Assignment",
    "body": "You have been assigned to job: {{job_title}}",
    "type": "job_assigned",
    "variables": ["job_title"]
}
```

#### 3. Send Broadcast Notification
```http
POST /api/management/notifications/broadcast/
Content-Type: application/json

{
    "subject": "System Maintenance",
    "message": "System will be down for maintenance",
    "recipients": "all", // or "clients" or "workers"
    "channel": "email" // or "sms" or "both"
}
```

#### 4. Get Notification Metrics
```http
GET /api/management/notifications/metrics/
```

**Query Parameters:**
- `start_date` (string): Start date (YYYY-MM-DD)
- `end_date` (string): End date (YYYY-MM-DD)
- `channel` (string): Filter by channel ('email', 'sms', 'both')

**Response (200 OK):**
```json
{
    "total_sent": 1000,
    "success_rate": 0.98,
    "delivery_time": {
        "average": 2.5,
        "p95": 5.0,
        "p99": 10.0
    },
    "channel_stats": {
        "email": {
            "total": 800,
            "success_rate": 0.99
        },
        "sms": {
            "total": 200,
            "success_rate": 0.95
        }
    },
    "error_breakdown": {
        "delivery_failed": 10,
        "invalid_recipient": 5,
        "rate_limited": 5
    }
}
```

### Recommendation System

The recommendation system provides two main endpoints for matching workers with jobs and vice versa.

#### 1. Get Recommended Workers for a Job
```http
GET /api/recommendations/jobs/{job_id}/workers/
```
Get recommended workers for a specific job. Only the job owner (client) can access this endpoint.

**Response (200 OK):**
```json
[
    {
        "id": 1,
        "job": {
            "id": 1,
            "title": "House Cleaning",
            "description": "Need house cleaning service",
            "location": "Addis Ababa",
            "status": "open",
            "created_at": "2024-03-15T10:00:00Z"
        },
        "worker": {
            "id": 1,
            "username": "jane.smith",
            "first_name": "Jane",
            "last_name": "Smith",
            "location": "Addis Ababa",
            "skills": [
                {
                    "name": "House Cleaning",
                    "level": "Expert"
                }
            ],
            "rating_stats": {
                "average_rating": 4.8,
                "total_ratings": 25
            }
        },
        "score": 0.95,
        "criteria": {
            "skill_match": 0.9,
            "location_match": 1.0,
            "rating_score": 0.96
        },
        "created_at": "2024-03-15T10:00:00Z"
    }
]
```

#### 2. Get Recommended Jobs for a Worker
```http
GET /api/recommendations/workers/jobs/
```
Get recommended jobs for the authenticated worker.

**Response (200 OK):**
```json
[
    {
        "id": 1,
        "job": {
            "id": 1,
            "title": "House Cleaning",
            "description": "Need house cleaning service",
            "location": "Addis Ababa",
            "status": "open",
            "created_at": "2024-03-15T10:00:00Z"
        },
        "worker": {
            "id": 1,
            "username": "jane.smith",
            "first_name": "Jane",
            "last_name": "Smith",
            "location": "Addis Ababa",
            "skills": [
                {
                    "name": "House Cleaning",
                    "level": "Expert"
                }
            ],
            "rating_stats": {
                "average_rating": 4.8,
                "total_ratings": 25
            }
        },
        "score": 0.95,
        "criteria": {
            "skill_match": 0.9,
            "location_match": 1.0,
            "rating_score": 0.96
        },
        "created_at": "2024-03-15T10:00:00Z"
    }
]
```

**Important Notes:**
- Both endpoints require authentication
- The job-worker recommendation endpoint is only accessible to the job owner
- The worker-jobs recommendation endpoint is only accessible to workers
- Results are cached for better performance
- Each endpoint returns up to 5 best matches
- The score ranges from 0 to 1, where 1 is the best match
- The criteria object shows the breakdown of how the score was calculated

## Error Responses

All endpoints may return the following error responses:

### 400 Bad Request
```json
{
    "error": "Invalid request data"
}
```

### 401 Unauthorized
```json
{
    "detail": "Authentication credentials were not provided."
}
```

### 403 Forbidden
```json
{
    "error": "You do not have permission to perform this action."
}
```

### 404 Not Found
```json
{
    "error": "Resource not found"
}
```

## Rate Limiting

- Admin endpoints: 60 requests per minute
- Exceeding limits will result in 429 Too Many Requests response

## Best Practices

1. **Security**
   - Always use HTTPS
   - Store tokens securely
   - Implement proper error handling
   - Validate all input data
   - Use CSRF protection for state-changing requests

2. **Performance**
   - Implement caching where appropriate
   - Use pagination for list endpoints
   - Monitor API usage

3. **Error Handling**
   - Implement proper error handling
   - Log errors for debugging
   - Provide meaningful error messages
   - Handle network errors gracefully

4. **Testing**
   - Test all endpoints thoroughly
   - Verify admin workflows
   - Test error scenarios
   - Validate notification handling

### Jobs API

The jobs API provides endpoints for managing jobs, applications, and job-related operations.

#### 1. Create Job
```http
POST /jobs/
Content-Type: multipart/form-data

{
    "title": "House Cleaning",
    "location": "Addis Ababa",
    "skills": "House Cleaning",
    "description": "Need house cleaning service",
    "category_id": 1,
    "payment_method": "telebirr",
    "uploaded_images": [file1, file2] // Optional
}
```
Create a new job posting. Only clients can create jobs.

**Response (201 Created):**
```json
{
    "id": 1,
    "title": "House Cleaning",
    "location": "Addis Ababa",
    "skills": "House Cleaning",
    "description": "Need house cleaning service",
    "category_id": 1,
    "payment_method": "telebirr",
    "status": "open",
    "created_at": "2024-03-15T10:00:00Z",
    "images": [
        "https://api.skillconnect.wisewaytech.com/media/jobs/image1.jpg",
        "https://api.skillconnect.wisewaytech.com/media/jobs/image2.jpg"
    ]
}
```

#### 2. List Jobs (Client)
```http
GET /jobs/
```
List all jobs created by the authenticated client.

**Response (200 OK):**
```json
[
    {
        "id": 1,
        "title": "House Cleaning",
        "location": "Addis Ababa",
        "skills": "House Cleaning",
        "description": "Need house cleaning service",
        "payment_method": "telebirr",
        "status": "open",
        "created_at": "2024-03-15T10:00:00Z"
    }
]
```

#### 3. List Open Jobs (Worker)
```http
GET /jobs/open/
```
List all open jobs that workers can apply to.

**Response (200 OK):**
```json
[
    {
        "id": 1,
        "title": "House Cleaning",
        "location": "Addis Ababa",
        "skills": "House Cleaning",
        "description": "Need house cleaning service",
        "payment_method": "telebirr",
        "status": "open",
        "created_at": "2024-03-15T10:00:00Z"
    }
]
```

#### 4. Get Job Details
```http
GET /jobs/{id}/
```
Get detailed information about a specific job.

**Response (200 OK):**
```json
{
    "id": 1,
    "title": "House Cleaning",
    "location": "Addis Ababa",
    "skills": "House Cleaning",
    "description": "Need house cleaning service",
    "category_id": 1,
    "payment_method": "telebirr",
    "status": "open",
    "created_at": "2024-03-15T10:00:00Z",
    "images": [
        "https://api.skillconnect.wisewaytech.com/media/jobs/image1.jpg",
        "https://api.skillconnect.wisewaytech.com/media/jobs/image2.jpg"
    ],
    "client": {
        "id": 1,
        "username": "john.doe",
        "first_name": "John",
        "last_name": "Doe",
        "rating_stats": {
            "average_rating": 4.5,
            "total_ratings": 10
        }
    }
}
```

#### 5. Update Job
```http
PUT /jobs/{id}/
Content-Type: multipart/form-data

{
    "title": "Updated House Cleaning",
    "location": "Addis Ababa",
    "skills": "House Cleaning",
    "description": "Updated description",
    "category_id": 1,
    "payment_method": "telebirr",
    "uploaded_images": [file1, file2] // Optional
}
```
Update an existing job. Only the job owner can update it.

**Response (200 OK):**
```json
{
    "id": 1,
    "title": "Updated House Cleaning",
    "location": "Addis Ababa",
    "skills": "House Cleaning",
    "description": "Updated description",
    "category_id": 1,
    "payment_method": "telebirr",
    "status": "open",
    "created_at": "2024-03-15T10:00:00Z",
    "images": [
        "https://api.skillconnect.wisewaytech.com/media/jobs/image1.jpg",
        "https://api.skillconnect.wisewaytech.com/media/jobs/image2.jpg"
    ]
}
```

#### 6. Delete Job
```http
DELETE /jobs/{id}/
```
Delete a job. Only the job owner can delete it.

**Response (204 No Content)**

#### 7. Apply to Job
```http
POST /jobs/{id}/apply/
Content-Type: application/json

{
    "action": "apply" // or "withdraw" to withdraw application
}
```
Apply to an open job or withdraw an existing application. Only workers can apply.

**Response (201 Created):**
```json
{
    "id": 1,
    "job": 1,
    "worker": 1,
    "status": "pending",
    "created_at": "2024-03-15T10:00:00Z"
}
```

#### 8. List Job Applications
```http
GET /jobs/{id}/applications/
```
List all applications for a specific job. Only the job owner can view applications.

**Response (200 OK):**
```json
[
    {
        "id": 1,
        "job": 1,
        "worker": {
            "id": 1,
            "username": "jane.smith",
            "first_name": "Jane",
            "last_name": "Smith",
            "skills": [
                {
                    "name": "House Cleaning",
                    "level": "Expert"
                }
            ],
            "rating_stats": {
                "average_rating": 4.8,
                "total_ratings": 25
            }
        },
        "status": "pending",
        "created_at": "2024-03-15T10:00:00Z"
    }
]
```

#### 9. Respond to Application
```http
POST /jobs/{job_id}/applications/{application_id}/respond/
Content-Type: application/json

{
    "status": "accepted" // or "rejected"
}
```
Accept or reject a worker's application. Only the job owner can respond.

**Response (200 OK):**
```json
{
    "id": 1,
    "job": 1,
    "worker": 1,
    "status": "accepted",
    "created_at": "2024-03-15T10:00:00Z"
}
```

#### 10. Mark Job as Completed
```http
PUT /jobs/{id}/status/
Content-Type: application/json

{
    "status": "completed"
}
```
Mark a job as completed. Both client and worker must mark the job as completed.

**Response (200 OK):**
```json
{
    "id": 1,
    "title": "House Cleaning",
    "status": "completed",
    "completed_at": "2024-03-15T10:00:00Z"
}
```

#### 11. Submit Job Feedback
```http
POST /jobs/{id}/feedback/
Content-Type: application/json

{
    "rating": 5,
    "review": "Excellent service!"
}
```
Submit feedback for a completed job. Rating must be between 1 and 5.

**Response (201 Created):**
```json
{
    "id": 1,
    "job": 1,
    "rating": 5,
    "review": "Excellent service!",
    "created_at": "2024-03-15T10:00:00Z"
}
```

#### 12. Get Job Reviews
```http
GET /jobs/{id}/reviews/
```
Get all reviews for a specific job.

**Response (200 OK):**
```json
{
    "worker_feedback": {
        "rating": 5,
        "review": "Great client!",
        "created_at": "2024-03-15T10:00:00Z"
    },
    "client_feedback": {
        "rating": 5,
        "review": "Excellent service!",
        "created_at": "2024-03-15T10:00:00Z"
    }
}
```

**Important Notes:**
- All endpoints require authentication
- Job creation and management is restricted to clients
- Job applications are restricted to workers
- Job status transitions: open -> in_progress -> completed
- Both client and worker must mark the job as completed
- Feedback can only be submitted for completed jobs
- Images are optional but recommended for better job visibility
- Payment methods supported: telebirr, chapa, e_birr, cash

### Users API

The users API provides endpoints for authentication, user management, and profile operations.

#### 1. Login
```http
POST /users/auth/login/
Content-Type: application/json

{
    "identifier": "email@example.com", // or phone number
    "password": "your_password"
}
```

**Response (200 OK):**
```json
{
    "token": "your_auth_token",
    "user": {
        "id": 1,
        "username": "john.doe",
        "first_name": "John",
        "last_name": "Doe",
        "role": "client", // or "worker"
        "email": "email@example.com",
        "phone_number": "+251911123456"
    }
}
```

#### 2. Signup Process

##### 2.1. Initiate Signup
```http
POST /users/auth/signup/initiate/
Content-Type: application/json

{
    "signup_method": "email" // or "phone"
}
```

**Response (200 OK):**
```json
{
    "user_id": 1,
    "message": "Signup method selected"
}
```

##### 2.2. Request Verification Code
```http
POST /users/auth/signup/request-code/
Content-Type: application/json

{
    "identifier": "email@example.com", // or phone number
    "user_id": 1
}
```

**Response (200 OK):**
```json
{
    "message": "Verification code sent or resent"
}
```

##### 2.3. Complete Signup
```http
POST /users/auth/signup/complete/
Content-Type: application/json

{
    "user_id": 1,
    "verification_code": "123456",
    "username": "john.doe",
    "password": "your_password",
    "first_name": "John",
    "last_name": "Doe",
    "role": "client" // or "worker"
}
```

**Response (201 Created):**
```json
{
    "token": "your_auth_token",
    "user": {
        "id": 1,
        "username": "john.doe",
        "first_name": "John",
        "last_name": "Doe",
        "role": "client",
        "email": "email@example.com",
        "phone_number": "+251911123456"
    }
}
```

#### 3. Password Reset

##### 3.1. Request Password Reset
```http
POST /users/auth/password-reset/
Content-Type: application/json

{
    "identifier": "email@example.com" // or phone number
}
```

**Response (200 OK):**
```json
{
    "message": "Password reset code sent"
}
```

##### 3.2. Confirm Password Reset
```http
POST /users/auth/password-reset/confirm/
Content-Type: application/json

{
    "identifier": "email@example.com", // or phone number
    "verification_code": "123456",
    "new_password": "new_password"
}
```

**Response (200 OK):**
```json
{
    "message": "Password reset successful"
}
```

#### 4. User Profile

##### 4.1. Get Profile
```http
GET /users/profile/
```

**Response (200 OK):**
```json
{
    "id": 1,
    "username": "john.doe",
    "first_name": "John",
    "last_name": "Doe",
    "role": "client",
    "email": "email@example.com",
    "phone_number": "+251911123456"
}
```

##### 4.2. Update Client Profile
```http
PUT /users/profile/client/
Content-Type: application/json

{
    "first_name": "John",
    "last_name": "Doe",
    "email": "email@example.com",
    "phone_number": "+251911123456"
}
```

**Response (200 OK):**
```json
{
    "id": 1,
    "username": "john.doe",
    "first_name": "John",
    "last_name": "Doe",
    "role": "client",
    "email": "email@example.com",
    "phone_number": "+251911123456"
}
```

##### 4.3. Update Worker Profile
```http
PUT /users/profile/worker/
Content-Type: application/json

{
    "first_name": "John",
    "last_name": "Doe",
    "email": "email@example.com",
    "phone_number": "+251911123456",
    "location": "Addis Ababa",
    "skills": [
        {
            "name": "House Cleaning",
            "level": "Expert"
        }
    ],
    "profile_pic": "base64_encoded_image" // Optional
}
```

**Response (200 OK):**
```json
{
    "id": 1,
    "username": "john.doe",
    "first_name": "John",
    "last_name": "Doe",
    "role": "worker",
    "email": "email@example.com",
    "phone_number": "+251911123456",
    "location": "Addis Ababa",
    "skills": [
        {
            "name": "House Cleaning",
            "level": "Expert"
        }
    ],
    "profile_pic": "https://api.skillconnect.wisewaytech.com/media/profiles/pic.jpg",
    "rating_stats": {
        "average_rating": 4.5,
        "total_ratings": 10
    }
}
```

#### 5. User Ratings and Reviews

##### 5.1. Get User Rating Stats
```http
GET /users/{user_id}/ratings/
```

**Response (200 OK):**
```json
{
    "average_rating": 4.5,
    "total_ratings": 10,
    "rating_breakdown": {
        "5_star": 5,
        "4_star": 3,
        "3_star": 1,
        "2_star": 1,
        "1_star": 0
    }
}
```

##### 5.2. Get User Reviews
```http
GET /users/{user_id}/reviews/
```

**Response (200 OK):**
```json
[
    {
        "id": 1,
        "job": {
            "id": 1,
            "title": "House Cleaning"
        },
        "rating": 5,
        "review": "Excellent service!",
        "created_at": "2024-03-15T10:00:00Z",
        "reviewer": {
            "id": 2,
            "username": "jane.smith",
            "first_name": "Jane",
            "last_name": "Smith"
        }
    }
]
```

#### 6. Payment Preferences

##### 6.1. Get/Update Payment Preference
```http
GET /users/payment-preference/
PUT /users/payment-preference/
Content-Type: application/json

{
    "payment_method": "cash" // or "chapa"
}
```

**Response (200 OK):**
```json
{
    "payment_method": "cash"
}
```

**Important Notes:**
- All endpoints except authentication endpoints require a valid token
- Token should be included in the Authorization header: `Authorization: Token your_auth_token`
- Signup process is two-step: initiate -> verify -> complete
- Password reset process is two-step: request code -> verify and reset
- Profile updates are role-specific (client vs worker)
- Worker profiles include additional fields like skills and location
- Rating stats and reviews are available for both clients and workers
- Payment preferences can be set to either cash or chapa
