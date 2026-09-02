# PR Merge Template

## 1. Change Description

- **Reason for Change:**
- **Change Content:**
- [ ] **Involves code dual-merge** (attach the other PR link):

----

## 2. Function Verification

- [ ] **Function self-verification**
- [ ] **Local self-verification sample screenshots** (ensure no personal information is shown)
- [ ] **Smoke test passed**

----

## 3. Code Review

- **Requirements:**
  - If the merged code exceeds 200 lines, a review meeting with three or more reviewers is required.
  - The review density must be at least 2 comments per 100 lines.
  - If the review defect density does not meet the requirement, an explanation must be provided.
  - Code exceeding 1000 lines is not allowed to be merged in principle; a record must be filed.
- [ ] **Code review completed**
- [ ] **UT test case coverage provided**

----

## 4. Security Self-Check

**Typical Security Coding Issues**

- [ ] **If external interfaces are involved, has external data been validated**
- [ ] **Are the MR title and description filled in the required format**
- [ ] **Is null pointer validation performed**
- [ ] **Is return value validation performed**
- [ ] **Are file permission configurations properly considered**
- [ ] **Are exception scenarios of interfaces fully considered**
- [ ] **Are error logs correctly recorded**
- [ ] **If regular expressions are involved, has ReDoS validation been performed on the regular expressions**
- [ ] **If operations are involved, are there risks such as integer overflow or division by zero**

----

## 5. Change Notification

- **Documentation changes:**
- **Change notification (message notification + email notification):**

----

## 6. Smoke Test Changes

- **PR source:**
  - [ ] Issue
  - [ ] Feature
  - [ ] Security review
  - [ ] Other
- [ ] **Is there a case where the smoke test could have caught an issue but did not**
- [ ] **Does a smoke test need to be added:**

----
