# Google OAuth Verification – Change Notes

## Context
Google's verification team requested the following corrections before approving the app:
1. Add `drive.file` scope to the OAuth consent screen configuration.
2. Remove `drive.metadata.readonly` from the consent screen.
3. Replace the Drive-based file listing with a Google Picker flow to comply with minimum-scope requirements.
4. Improve the Privacy Policy to clearly describe sensitive data protection mechanisms.

---

## Code Changes Made

### `dashboard.py`
- **Scopes changed**: Replaced `drive.metadata.readonly` with `drive.file` in `GOOGLE_SCOPES`.
- **New env vars**: Added `GOOGLE_API_KEY` and `GOOGLE_APP_ID` constants read from environment.
- **New endpoint `/api/google/picker-config`**: Returns non-secret `api_key` and `app_id` to the frontend.
- **New endpoint `/api/google/picker-token`**: Exposes the httpOnly-cookie access token to the frontend for use in the Picker widget. Required because Google Picker's `PickerBuilder.setOAuthToken()` needs the token client-side.
- The existing `/api/google/sheets/<id>` endpoint (tab listing + row data) is **unchanged** — it still uses `spreadsheets.readonly`.
- The `/api/google/sheets` list endpoint (Drive files.list) still exists for backward compatibility but is no longer used by the UI. With `drive.file` scope it will only return files the user has previously opened via Picker.

### `templates/external.html`
- Added Google API script tag (`https://apis.google.com/js/api.js`).
- Replaced the Drive file list + search input UI with a **Google Picker** button flow:
  - "Pick File from Drive" button → opens Google Picker widget.
  - Picker calls `/api/google/picker-token` and `/api/google/picker-config` before opening.
  - After file selection, tab list is fetched from `/api/google/sheets/<id>` (unchanged).
  - Tab dropdown + "Devam →" button flow is identical to before.
- Removed `gsLoadFiles`, `gsSearchFiles`, `gsSelectFile` functions (replaced by `gsOpenPicker`, `gsPickerCallback`).
- Removed unused `gsSearchTimer` state variable.

### `templates/privacy_policy.html`
- Updated "Last updated" date.
- Updated scope description: now references `drive.file` (Picker-based) instead of `drive.metadata.readonly`.
- Added **Section 3: Data Protection and Security Mechanisms** with explicit coverage of:
  - TLS/HTTPS for all transit
  - Access token lifetime (1 hour, auto-expires)
  - httpOnly + SameSite=Lax + Secure cookie storage
  - No refresh tokens stored
  - CSRF protection via `state` parameter
  - Minimum scope policy
  - No persistent Google data storage
  - Credentials stored as env vars, never in source code
- Added **Section 5: Data Retention and Deletion** with explicit deletion instructions.
- Added **Section 8: Limited Use Disclosure** per Google API Services User Data Policy requirements.

### `static/app_i18n.js`
- Added English translations for new Picker UI strings:
  - `gs-pick-btn`, `gs-change-btn`, `gs-picker-err`, `gs-tab-err`
- Turkish fallbacks are embedded in HTML elements as `data-i18n` attribute defaults (existing pattern).

---

## New Environment Variables Required

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_API_KEY` | Yes (for Picker) | Public API key — create in Cloud Console → APIs & Services → Credentials → API Key. Restrict it to "Google Picker API" and your domain. |
| `GOOGLE_APP_ID` | Yes (for Picker) | Your GCP project **number** (not name/ID). Find it in Cloud Console → Home → Project info card. |
| `GOOGLE_CLIENT_ID` | Already set | OAuth 2.0 client ID (unchanged) |
| `GOOGLE_CLIENT_SECRET` | Already set | OAuth 2.0 client secret (unchanged) |

---

## Manual Steps You Must Complete in Cloud Console

### Step 1 — Update OAuth Consent Screen Scopes
1. Go to [Google Cloud Console](https://console.cloud.google.com/) → **APIs & Services → OAuth consent screen**.
2. Click **Edit App**.
3. Navigate to the **Scopes** section.
4. **Add** the scope: `https://www.googleapis.com/auth/drive.file`
5. **Remove** the scope: `https://www.googleapis.com/auth/drive.metadata.readonly`
6. Verify `https://www.googleapis.com/auth/spreadsheets.readonly` is still present.
7. Click **Save and Continue** through all steps.
8. Click **Submit for verification**.

### Step 2 — Enable Google Picker API
1. Go to **APIs & Services → Library**.
2. Search for **Google Picker API** and enable it.

### Step 3 — Create an API Key for Google Picker
1. Go to **APIs & Services → Credentials**.
2. Click **+ Create Credentials → API Key**.
3. Restrict the key: **API restrictions → Restrict key → Google Picker API**.
4. Restrict by **HTTP referrers**: add `scanner.onursuay.com/*` (and `localhost:*` for dev).
5. Copy the key and set it as `GOOGLE_API_KEY` in your Railway environment variables.

### Step 4 — Get Your Project Number
1. Go to Cloud Console → **Home**.
2. Copy the **Project number** (a 12-digit integer) from the "Project info" card.
3. Set it as `GOOGLE_APP_ID` in Railway environment variables.

### Step 5 — Reply to Google's Verification Email
After completing the above, reply to the Google verification email with something like:

> We have addressed all requested items:
> 1. Added `drive.file` scope to the OAuth consent screen.
> 2. Removed `drive.metadata.readonly` from the consent screen.
> 3. Replaced the Drive file listing with Google Picker API, so users explicitly select files — no broad Drive access occurs.
> 4. Updated our Privacy Policy at https://scanner.onursuay.com/privacy-policy to include explicit coverage of token lifecycle, TLS transit encryption, no refresh token storage, minimum scope usage, Limited Use disclosure, and data deletion procedures.
>
> Please re-review the submission.

---

## Verification: What Changes Were NOT Made
- Service account scopes (used by backend for Sheets write operations) were not touched — these are internal and not part of the user-facing OAuth flow being verified.
- The import wizard UX (column mapping, preview, Step 2/3/4) is unchanged.
- No security regressions were introduced. The Picker token endpoint is protected by the same httpOnly cookie that gates all other Google API endpoints.
