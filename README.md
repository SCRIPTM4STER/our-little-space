# Our Little Space

A mobile-friendly Django and React application for two or more people to hang out online. The planned experience combines rooms, chat, shared watching, and small multiplayer games in one playful space.

## Project Status

### Implemented

- Django 6.1 and Django REST Framework backend.
- SQLite database configured for local development.
- React 19 frontend powered by Vite.
- React Router routes for the home page, group rooms, DMs, friend requests, and notifications.
- Shared responsive navbar on every frontend route.
- Combined social activity popover for notifications, unread direct messages, and pending friend requests.
- Mobile navigation menu with accessible toggle attributes.
- Home page visual sections:
	- Hero section.
	- Watch/video placeholder.
	- Chat mockup.
	- Games mockup.
	- Footer.
- Responsive Rooms page with a show/hide member list.
- Backend health endpoint at `/api/health/`.
- Development CORS configuration for the Vite server.
- Token-based authentication with register, login, current-user, and logout endpoints.
- Frontend API request helper with automatic authentication headers.
- Frontend auth provider with persisted login state.
- Login and registration screens at `/login` and `/register`.
- Room routes protected by authentication.
- Database-backed group rooms with membership and member-only group messages.
- Room and direct messages render live while their view is open using incremental REST polling; outgoing messages render immediately.
- Private, invite-only room discovery with friend invitations, pending invite notifications, accept/decline actions, and owner-only room deletion.
- Separate one-to-one conversations, friend requests, and notification inbox.
- Search for friends by exact, case-insensitive `@username` and confirm the public profile before sending a request.
- Separate one-to-one user profiles with display name, username, bio, and avatar.
- Authenticated profile retrieval and multipart profile editing at `/api/profile/`.
- Profile page and editor at `/profile` and `/profile/edit`.
- Navbar avatar account control with fallback initials and profile logout action.
- Backend authentication and profile tests.

### Currently Mocked or Incomplete

- Room and direct messages poll for new message IDs every 1.8 seconds while their conversation is open. WebSocket delivery is not implemented.
- The current room owner must delete their room to close it; ownership transfer is not implemented.
- The home-page chat, video controls, and game buttons remain visual prototypes.
- Video controls do not control a real video or synchronize playback.
- Game buttons do not launch playable games.
- The current auth token is stored in browser `localStorage`; production should consider an HTTP-only cookie strategy.

## Technology

### Frontend

- React
- React Router
- Vite
- Tailwind CSS Vite integration
- Custom CSS using the Baloo 2 and Nunito fonts

### Backend

- Python
- Django
- Django REST Framework
- SQLite
- `django-cors-headers`

## Project Structure

```text
backend/
	manage.py
	db.sqlite3
	api/
		models.py       # Profiles, friendships, DMs, notifications, and group rooms
		serializers.py  # Auth and domain serializers
		views.py        # Auth, social, messaging, and room API views
		signals.py      # Automatic profile creation
		urls.py         # API routes
		tests.py        # Backend API and model tests
	config/
		settings.py
		urls.py

frontend/
	src/
		App.jsx
		App.css
		main.jsx
		Pages/Rooms.jsx
		Pages/Profile.jsx
		Pages/ProfileEdit.jsx
		api/client.js
		auth/
		assets/components/navbar.jsx
```

## Environment Setup

- Copy `backend/.env.example` to `backend/.env` and set local backend values, including a private `SECRET_KEY`.
- Copy `frontend/.env.example` to `frontend/.env` for the local Vite API URL.
- SQLite is the default local database. The backend `.env` uses `DATABASE_URL=sqlite:///db.sqlite3`.
- PostgreSQL can be enabled later by changing `DATABASE_URL` to a PostgreSQL connection string; the PostgreSQL driver is included in backend requirements. A running PostgreSQL server is not needed for local SQLite development.
- Never commit either `.env` file. The `.env.example` files contain safe examples only.
- `VITE_API_URL` is frontend configuration exposed to the browser, not a secret. It should contain only the backend origin, such as `http://127.0.0.1:8000`.

Backend variables:

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Required private Django signing key. |
| `DEBUG` | Development diagnostics; must be `False` in production. |
| `ALLOWED_HOSTS` | Comma-separated backend hostnames. |
| `CORS_ALLOWED_ORIGINS` | Comma-separated exact frontend origins. |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated trusted origins; use HTTPS origins in production. |
| `DATABASE_URL` | SQLite or PostgreSQL connection URL. |
| `SECURE_SSL_REDIRECT` | Redirect HTTP to HTTPS when HTTPS is available. |
| `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` | Require cookies to travel over HTTPS. |
| `SECURE_HSTS_SECONDS`, `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD` | HSTS policy; enable only after HTTPS is confirmed for the domain. |
| `SECURE_PROXY_SSL_HEADER` | Optional trusted proxy header, e.g. `HTTP_X_FORWARDED_PROTO,https`; use only if the proxy overwrites it. |
| `STATIC_ROOT`, `MEDIA_ROOT`, `STATIC_URL`, `MEDIA_URL` | Optional static and uploaded-media locations/URLs. |
| `X_FRAME_OPTIONS`, `SECURE_REFERRER_POLICY`, `LOG_LEVEL` | Response security policy and console log level. |
| `VITE_API_URL` | Browser-visible backend origin. Never put secrets in `VITE_` variables. |

## Local Development

### Backend

From the project root, open a terminal and run:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

The backend runs at `http://127.0.0.1:8000/`. Daphne is enabled as the ASGI development server, so this command serves the room-watch WebSocket as well as HTTP requests.

Health check:

```text
GET http://127.0.0.1:8000/api/health/
```

Expected response:

```json
{
	"status": "ok",
	"service": "backend"
}
```

### Frontend

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

The frontend runs at `http://localhost:5173/`.

### Access Through the Dev Tunnel

Keep Django running on port 8000 and Vite running on port 5173. Vite proxies `/api`, `/media`, and `/ws` to Django, so the browser can use the frontend tunnel URL for API and WebSocket traffic without exposing a second tunnel. Restart Vite after changing `vite.config.js`, then reopen `https://w9460k8k-5173.inc1.devtunnels.ms/`. If the tunnel hostname changes, update `server.allowedHosts` in `vite.config.js` to match it. During development, a localhost `VITE_API_URL` automatically uses this proxy.

Useful frontend commands:

```powershell
npm run build
npm run lint
```

The production build passes. Full-project lint completes with React hook warnings in several existing and touched components. Backend checks and API tests pass when run with `backend/.venv`.

## Frontend Routes

| Route | Purpose | Status |
| --- | --- | --- |
| `/` | Home page with watch, chat, and games sections | Visual prototype |
| `/rooms` | Create private rooms, invite friends, and chat as a member | Implemented |
| `/Rooms` | Legacy case variant of the Rooms route | Supported for compatibility |
| `/messages` | Direct messages with friends | Implemented |
| `/friend-requests` | Find users by `@username`, send requests, and respond to requests | Implemented |
| `/notifications` | View and mark notifications as read | Implemented |
| `/login` | User login | Implemented |
| `/register` | User registration | Implemented |
| `/profile` | Current user profile | Implemented |
| `/profile/edit` | Edit current user profile | Implemented |

## Backend API

| Endpoint | Method | Purpose | Status |
| --- | --- | --- | --- |
| `/api/health/` | `GET` | Confirm that the backend is running | Implemented |
| `/admin/` | `GET` | Django administration | Available after creating a superuser |
| `/api/auth/register/` | `POST` | Create a user and return a token | Implemented |
| `/api/auth/login/` | `POST` | Authenticate a user and return a token | Implemented |
| `/api/auth/me/` | `GET` | Return the authenticated user | Implemented |
| `/api/auth/logout/` | `POST` | Revoke the current token | Implemented |
| `/api/profile/` | `GET` | Retrieve the authenticated user's profile | Implemented |
| `/api/profile/` | `PATCH` | Update username, display name, bio, or avatar | Implemented |
| `/api/users/search/?username={username}` | `GET` | Find an exact username match and return its public profile | Implemented |
| `/api/activity/summary/` | `GET` | Return unread notification, message, and pending friend-request counts | Implemented |
| `/api/rooms/` | `GET`, `POST` | List rooms the user belongs to or create a room | Implemented |
| `/api/rooms/{id}/` | `DELETE` | Delete a room as its owner | Implemented |
| `/api/rooms/{id}/join/` | `POST` | Confirm existing membership; joining requires an invitation | Implemented |
| `/api/rooms/{id}/leave/` | `POST` | Leave a group room | Implemented |
| `/api/rooms/{id}/messages/` | `GET`, `POST` | Read or send messages as a room member | Implemented |
| `/api/rooms/{id}/invitations/` | `GET`, `POST` | List pending room invites or invite a friend as a member | Implemented |
| `/api/room-invitations/` | `GET` | List the current user's pending room invitations | Implemented |
| `/api/room-invitations/{id}/accept/` | `POST` | Accept an invitation and join its room | Implemented |
| `/api/room-invitations/{id}/decline/` | `POST` | Decline an invitation | Implemented |
| `/api/conversations/` | `GET`, `POST` | List conversations or start a DM with a friend | Implemented |
| `/api/conversations/{id}/messages/` | `GET`, `POST` | Read or send a direct message | Implemented |
| `/api/friend-requests/` | `GET`, `POST` | List requests or send a request | Implemented |
| `/api/friend-requests/received/` | `GET` | List pending incoming requests | Implemented |
| `/api/friend-requests/sent/` | `GET` | List pending outgoing requests | Implemented |
| `/api/friend-requests/{id}/accept/` | `POST` | Accept an incoming request | Implemented |
| `/api/friend-requests/{id}/reject/` | `POST` | Reject an incoming request | Implemented |
| `/api/notifications/` | `GET` | List notifications and unread count | Implemented |
| `/api/notifications/{id}/read/` | `POST` | Mark a notification read | Implemented |

Profile updates use `multipart/form-data` when uploading an avatar. Avatars must be valid images no larger than 5 MB.

Authentication endpoints use the `Authorization` header:

```text
Authorization: Token <token>
```

Registration request:

```json
{
	"username": "riyad",
	"email": "riyad@example.com",
	"password": "strong-password-123",
	"password_confirmation": "strong-password-123"
}
```

Successful register and login responses use this shape:

```json
{
	"data": {
		"token": "...",
		"user": {
			"id": 1,
			"username": "riyad",
			"email": "riyad@example.com",
			"first_name": "",
			"last_name": ""
		}
	}
}
```

The frontend can call the API through `src/api/client.js`:

```js
import { apiGet, apiPost } from './api/client'

const rooms = await apiGet('/rooms/')
await apiPost('/rooms/', { name: 'Movie night' })
```

Set `VITE_API_URL` when the backend is not running at the local default:

```text
VITE_API_URL=http://127.0.0.1:8000
```

## Production Preparation

The repository has generic production configuration but has not been deployed. Before serving traffic:

- Set `DEBUG=False`, a unique high-entropy `SECRET_KEY`, production `ALLOWED_HOSTS`, explicit HTTPS CORS origins, and HTTPS CSRF trusted origins in the backend environment.
- Use PostgreSQL by setting `DATABASE_URL` to the production connection URL. SQLite remains the local default. Run migrations explicitly against the selected database.
- Enable HTTPS redirects, secure cookies, and HSTS only after HTTPS and proxy behavior are verified. Set `SECURE_PROXY_SSL_HEADER` only when the trusted proxy overwrites the forwarded protocol header.
- Serve Django through an ASGI server for WebSocket features. For example, run `daphne -b 0.0.0.0 -p $PORT config.asgi:application`; configure the ingress or reverse proxy to forward WebSocket upgrades. The WSGI `config.wsgi:application` entrypoint does not serve room-watch WebSockets.
- The current in-memory Channels layer works only within one backend process. Use a shared channel layer such as Redis if deploying multiple backend processes or replicas; Redis is not required for a single-process local setup.
- Run `python manage.py collectstatic --noinput`; WhiteNoise serves collected Django static assets. Build the Vite app with `npm ci` and `npm run build`, serve `frontend/dist`, and configure the frontend host to route app paths to `index.html`.
- Store uploads on persistent media storage and serve them separately from static assets. The current filesystem backend needs a persistent volume and a safe media-serving policy.
- The default Django local-memory cache makes throttles process-local. A shared cache is required for reliable rate limits across multiple backend instances. Configure ingress request-body limits to complement the 5 MB avatar limit.
- The health endpoint is a lightweight liveness response, not a database/dependency readiness check. Keep application logs on stdout/stderr and monitor the service externally.
- Never commit `.env` files or expose backend secrets through Vite variables.

Generic service commands (the host must provide the runtime and process management):

```text
Backend:  daphne -b 0.0.0.0 -p $PORT config.asgi:application
Frontend: npm ci && npm run build
Migrate:  python manage.py migrate
Static:   python manage.py collectstatic --noinput
```

Deployment checklist: HTTPS, PostgreSQL, environment secrets, explicit host/CORS/CSRF allowlists, secure cookies, HSTS after HTTPS verification, persistent media, static asset serving, shared-cache throttling, logs, monitoring, and an explicit migration step. Token authentication remains unchanged; the frontend stores tokens in `localStorage`, and tokens do not expire automatically (logout revokes them).

## Recommended Development Roadmap

### 1. Scale message delivery if needed

- Consider WebSocket delivery if polling latency or traffic becomes a problem.

### 2. Add shared watching

- Add a real video source.
- Implement play, pause, seek, and current-time state.
- Synchronize playback state for all members in a room.

### 3. Implement games

- Start with Tic Tac Toe.
- Store game state and turns on the server.
- Add multiplayer synchronization.
- Add Cards and Would You Rather after the first game flow is stable.

### 4. Improve quality and deployment

- Add frontend component and end-to-end tests.
- Configure production-specific PostgreSQL, shared cache, persistent media storage, and frontend hosting.
- Add accessibility checks and mobile browser testing.

## Important Configuration Notes

- Development CORS currently allows `http://localhost:5173`, `http://127.0.0.1:5173`, and `http://127.0.0.1:5174`.
- The backend currently uses SQLite for convenience during development.
- Django's secret key, debug mode, allowed hosts, CORS origins, CSRF trusted origins, and database URL are read from the backend environment.
- The frontend API client uses `VITE_API_URL`, defaulting to `http://127.0.0.1:8000`; it accepts either the backend origin or an origin ending in `/api`.
- Run backend checks with `backend/.venv\Scripts\python.exe` (Windows) to use the pinned project dependencies.
# our-little-space
