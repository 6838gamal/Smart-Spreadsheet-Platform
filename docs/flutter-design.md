# Smart Spreadsheet Platform — Flutter Mobile App Design Document

## 1. Overview

A production-ready Flutter mobile app for Android & iOS that brings the full power of the Smart Spreadsheet Platform to mobile users. Designed mobile-first — not a port of the web UI — with native feel, offline-first capabilities, and an embedded AI assistant.

---

## 2. Architecture

### Pattern
- **Clean Architecture** with **Feature-First** folder organization
- **MVVM** presentation layer (ViewModel = Riverpod Notifier)
- **Repository Pattern** separating data sources from domain logic
- **Dependency Injection** via Riverpod providers

### Layers (per feature)
```
feature/
  data/
    datasources/   ← API calls (Dio) + local cache (Hive)
    models/        ← JSON-serializable DTOs (Freezed + JsonSerializable)
    repositories/  ← implements domain repository interface
  domain/
    entities/      ← pure Dart classes (Freezed, no serialization)
    repositories/  ← abstract interfaces
    usecases/      ← single-responsibility business logic
  presentation/
    providers/     ← Riverpod Notifiers (state + actions)
    screens/       ← full-page widgets (GoRouter destinations)
    widgets/       ← reusable UI components scoped to feature
```

### Key Libraries
| Concern | Library |
|---|---|
| State | `flutter_riverpod` + `riverpod_annotation` |
| Navigation | `go_router` |
| Models | `freezed` + `json_serializable` |
| HTTP | `dio` |
| Local DB | `hive` |
| Secure Store | `flutter_secure_storage` |
| Offline detect | `connectivity_plus` |
| File pick | `file_picker` + `image_picker` |
| Permissions | `permission_handler` |
| Notifications | `flutter_local_notifications` |
| Biometrics | `local_auth` |
| Animations | `flutter_animate` + `lottie` |
| Charts | `fl_chart` |
| i18n | Flutter gen + ARB files (AR + EN) |

---

## 3. Project Structure

```
mobile/
├── assets/
│   ├── animations/      # Lottie JSON files
│   ├── fonts/           # Cairo font family (AR/EN)
│   ├── icons/           # SVG icons
│   └── images/          # static images
├── lib/
│   ├── main.dart        # entry point, Hive init, ProviderScope
│   ├── app.dart         # MaterialApp.router, theme, locale
│   ├── core/
│   │   ├── constants/   # API base URL, storage keys, app config
│   │   ├── di/          # global provider overrides
│   │   ├── error/       # Failure sealed classes + Exceptions
│   │   ├── network/     # DioClient with auth interceptor + retry
│   │   ├── router/      # GoRouter with redirect guards
│   │   ├── storage/     # HiveStorage + SecureStorage wrappers
│   │   ├── theme/       # Material 3, dynamic color, light/dark
│   │   ├── l10n/        # ARB files for AR + EN
│   │   └── utils/       # extensions, formatters, validators
│   ├── features/
│   │   ├── splash/      # startup, config load, auth check
│   │   ├── auth/        # login, register, PIN, biometric
│   │   ├── home/        # dashboard, quick actions, stats
│   │   ├── files/       # file manager (all sections)
│   │   ├── conversion/  # file conversion workflows
│   │   ├── ai_assistant/# AI chat + document Q&A
│   │   ├── search/      # global smart search
│   │   ├── account/     # profile, subscription, devices
│   │   └── notifications/# notification center
│   └── shared/
│       ├── widgets/     # AppBar, BottomNav, cards, empty states
│       └── providers/   # theme provider, locale provider, connectivity
```

---

## 4. Screens & User Flows

### 4.1 Splash → Auth Flow
```
SplashScreen
  ├─ has token & valid → HomeScreen
  ├─ has token & biometric enabled → BiometricScreen → HomeScreen
  └─ no token → LoginScreen
       ├─ LoginScreen → HomeScreen
       └─ LoginScreen → RegisterScreen → HomeScreen
```

### 4.2 Main Shell (Bottom Navigation)
```
Shell
  ├─ [0] HomeTab
  ├─ [1] FilesTab
  ├─ [2] ConvertTab  (FAB-style center button)
  ├─ [3] AITab
  └─ [4] AccountTab
```

### 4.3 Home Screen
- **Quick Actions strip**: Convert, OCR, Analyze, AI Chat
- **Recent Files** horizontal scroll
- **Usage Stats**: files count, storage used, conversions today
- **Subscription card**: current plan + daily limit progress

### 4.4 Files Screen
- **Segments**: My Files / Recent / Favorites / Shared / Offline / Downloads / Trash
- **Grid/List toggle** with animated transition
- **Sort**: Name / Date / Size / Type
- **Filter**: file type chips
- **Swipe left**: Delete / Move to trash
- **Swipe right**: Favorite / Share
- **Long press**: multi-select mode
- **Drag & drop** (tablet/desktop)

### 4.5 Conversion Screen
- Category grid: PDF Tools / Images / Office Docs
- Pick source file → select target format → progress → result
- **Background conversion** with notification on completion
- Retry on failure

### 4.6 AI Assistant Screen
- Persistent chat interface
- Attach document (file picker / from My Files)
- Streaming responses (chunked HTTP)
- Message types: text, table, code, file reference
- Context: active file shown in AppBar
- Actions: summarize, extract tables, Q&A, generate report

### 4.7 Search Screen
- Full-text search across files + analyses
- Filter chips: file type, date range, size range
- Sort dropdown
- Results grouped by type

### 4.8 Account Screen
- **Profile**: avatar, name, email, edit
- **Subscription**: plan, usage meters, upgrade CTA
- **Security**: biometric toggle, PIN change, device list
- **Preferences**: language (AR/EN), theme, notifications
- **Storage**: cache size, clear cache
- **Logout**

---

## 5. Design System

### Colors (Material 3 Dynamic + static seed)
- Seed color: `#6750A4` (purple)
- Surface variants, tonal containers follow M3 spec
- Dark mode: `ColorScheme.fromSeed(brightness: Brightness.dark)`

### Typography
- Font family: **Cairo** (supports Arabic + Latin)
- Scale follows M3: displayLarge → labelSmall

### Spacing
- Base unit: 8dp. Spacing scale: 4, 8, 12, 16, 24, 32, 48

### Animations
- Page transitions: shared-element + fade
- List items: staggered `flutter_animate` slide-in
- Loading: `shimmer` skeleton screens
- Success/Error: `lottie` micro-animations

### RTL
- Full RTL support for Arabic; auto-detected from locale
- `Directionality` wraps entire app

---

## 6. Backend API Integration

The Flutter app connects to the FastAPI backend at `https://<host>/api/v1/`.

### Auth Endpoints
- `POST /auth/login` → JWT token
- `POST /auth/register`
- `POST /auth/logout`
- `GET /auth/me`

### Files Endpoints
- `GET /files/` — list with pagination
- `POST /files/upload` — multipart
- `DELETE /files/{id}`
- `GET /files/{id}/download`

### Conversion Endpoints
- `POST /conversion/convert` — starts async job
- `GET /conversion/status/{job_id}` — poll
- `GET /conversion/download/{job_id}`

### AI Endpoints
- `POST /ai/chat` — streaming chat
- `POST /ai/analyze` — document analysis
- `GET /ai/analyses/{file_id}`

---

## 7. Offline & Sync Strategy

- **Hive** stores: user profile, recent files metadata, favorites list, pending upload queue
- **Offline queue**: uploads/conversions enqueued locally, replayed when connectivity restored
- **ConnectivityPlus** watches network; banner shown when offline
- Downloaded files stored in app documents directory

---

## 8. Security

- JWT stored in `flutter_secure_storage` (Keychain/Keystore)
- Biometric auth via `local_auth` (Face ID / Fingerprint)
- PIN fallback encrypted with device key
- Auto-logout after configurable idle timeout
- Certificate pinning on DioClient (production)

---

## 9. Notifications

- **Conversion complete**: file name + "ready to download"
- **Analysis complete**: document name + summary snippet
- **Shared file**: sender name + file name
- **Quota warning**: "80% of daily limit reached"

---

## 10. Feature Rollout Plan

| Phase | Features |
|---|---|
| Phase 1 | Splash, Auth, Home, Bottom Nav shell |
| Phase 2 | Files manager (all sections) |
| Phase 3 | Conversion workflows |
| Phase 4 | AI Assistant (chat + analysis) |
| Phase 5 | Search, Notifications, Account |
| Phase 6 | Offline sync, Biometric, PIN |
| Phase 7 | Tablet/Foldable adaptive layouts |
