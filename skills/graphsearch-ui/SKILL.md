---
name: graphsearch-ui
description: Deep reference for the GraphSearch UI Next.js project at ~/dev/graphsearch_ui. Use when asked about the GraphSearch frontend, search, chatbot, auth, CMS, data models, routing, components, or build setup.
---

# GraphSearch UI

Comprehensive reference for the **GraphSearch UI** Next.js project located at `~/dev/graphsearch_ui`.

## Project Overview

GraphSearch UI is the public-facing web application of the EPFL Graph Data Platform. It visualizes and navigates a knowledge graph containing institutional and educational entities (people, publications, labs, courses, lectures, concepts, MOOCs, notebooks, exercises, startups, units, categories, widgets). It provides:

- Bilingual (EN/FR) entity detail pages.
- Full-text autocomplete and search over the knowledge graph.
- A conversational chatbot backed by a remote LLM service.
- A Payload CMS admin area for content managers.
- Microsoft / PocketCampus single sign-on for users.

The project is bootstrapped with `create-next-app` but heavily customized.

## Tech Stack

| Layer | Technology |
| --- | --- |
| Framework | Next.js 16 (App Router, Turbopack enabled) |
| Runtime / Language | Node.js, TypeScript 6, ES2022 |
| React | React 19 |
| Styling | Tailwind CSS 4, DaisyUI 5, `@tailwindcss/typography` |
| CSS preprocessor | Sass |
| PostCSS | `@tailwindcss/postcss` |
| Icons | `react-icons` |
| HTTP client | `ky` |
| Forms / UI helpers | `downshift`, `rc-slider`, `nprogress`, `react-toastify`, `nuqs`, `clsx` |
| Database ORM | Prisma 7 with `@prisma/adapter-mariadb` |
| Auth | `better-auth` + Microsoft Entra ID + custom PocketCampus SSO plugin |
| CMS | Payload CMS 3 (`@payloadcms/db-sqlite`, `@payloadcms/richtext-lexical`) |
| Search | Elasticsearch 9 (`@elastic/elasticsearch`) |
| AI / Chat | `ai` SDK 7, `@ai-sdk/react`, `@ai-sdk/openai-compatible` |
| i18n | `next-intl` v4 |
| Testing | Vitest 4 + `@vitejs/plugin-react` + jsdom + `@testing-library/react` |
| Monitoring | Sentry Next.js 10, Matomo |
| Lint | ESLint 9 + `eslint-config-next` |

## Directory Structure

```
~/dev/graphsearch_ui
├── .env
├── config.json                 # App config: roles, chatbot models, limits, sentry sampling
├── next.config.ts              # Next.js config + MDX + next-intl + Sentry + Payload wrapper
├── tsconfig.json               # Path aliases: @/* -> ./src/*, @payload-config, @/config.json
├── vitest.config.ts
├── prisma/
│   ├── graph/
│   │   ├── schema.prisma       # Huge knowledge-graph schema (MySQL/MariaDB)
│   │   └── prisma.config.ts    # MYSQL_URL_GRAPH
│   └── website/
│       ├── schema.prisma       # Auth + chat conversation schema
│       ├── prisma.config.ts    # MYSQL_URL_WEBSITE
│       └── migrations/
├── src/
│   ├── app/
│   │   ├── (graphsearch)/[locale]/       # Public locale-prefixed routes
│   │   │   ├── (search)/                 # Entity pages, search, widgets
│   │   │   ├── (account)/                # User chats, admin chats
│   │   │   ├── chat/                     # Chat redirects
│   │   │   ├── chatbot/                  # Full-page chatbot
│   │   │   └── layout.tsx                # Locale group layout
│   │   ├── (payload)/                    # Payload CMS routes
│   │   ├── api/chat/route.ts             # Chat streaming API
│   │   ├── sitemap.xml/route.ts          # Dynamic sitemap
│   │   ├── global-error.tsx
│   │   ├── globals.css, fonts.css
│   │   └── layout.tsx / manifest.ts / robots.ts
│   ├── components/           # Reusable React components
│   ├── contexts/             # React contexts (chatbot state)
│   ├── i18n/                 # next-intl routing + request config
│   ├── layouts/              # BaseLayout, DocumentLayout, DefaultLayout
│   ├── lib/                  # Low-level clients: auth, db, ES, fetch, cache, payload, SSO
│   ├── messages/             # en.json, fr.json translation files
│   ├── models/               # Data-access functions per entity
│   ├── payload/              # Payload collections, migrations, types, components
│   ├── schemas/              # Zod schemas for entities and search params
│   ├── services/             # Higher-level business logic (search, chat, faq, groups)
│   └── utils/                # Utility helpers (record localization, etc.)
```

## Routing & App Router

- Locale prefix required for public routes: `/en/person/:id`, `/fr/concept/:id`.
- `src/i18n/routing.ts` defines `locales: ["fr", "en"]` and `defaultLocale: "en"`.
- `src/i18n/navigation.ts` exports typed `Link`, `redirect`, `usePathname`, etc.
- Route groups organize pages without affecting URLs:
  - `(graphsearch)` — public site.
  - `(search)` — entity detail pages + search results.
  - `(account)` — authenticated user/admin sections.
  - `(payload)` — Payload CMS admin.
- Entity pages follow the pattern `/(search)/<type>/[id]/page.tsx` plus relation sub-routes and `components/`.
- `src/app/(graphsearch)/[locale]/chat/route.ts` and `chat/[prompt]/route.ts` redirect query params to the homepage chat widget (`/?p=...`).

## Internationalization

- Translations live in `src/messages/en.json` and `src/messages/fr.json`.
- `src/i18n/request.ts` resolves locale from the `[locale]` segment and loads the matching JSON.
- `global.d.ts` declares `next-intl` `AppConfig.Locale` from `routing.locales`.
- UI text should be added to both `en.json` and `fr.json`; fallbacks are not automatic.

## Data Layer

### Two Prisma Clients

`src/lib/db.ts` exports two clients:

- `website` — `PrismaClient` from `@/generated/prisma/website/client` (MariaDB adapter).
- `graph` — `PrismaClient` from `@/generated/prisma/graph/client` (MariaDB adapter).

Both are constructed with `@prisma/adapter-mariadb` and a parsed `MYSQL_URL_*`.

### Graph Database Schema (`prisma/graph/schema.prisma`)

The graph schema models a pre-computed knowledge graph. Key concepts:

- **`Profile`** (`Data_N_Object_T_PageProfile`) — a unified multilingual profile table shared by all entity types. Holds localized names, descriptions, external keys/URLs, visibility, and numeric/short-code identifiers.
- **Entity tables** — one table per type: `Category`, `Concept`, `Course`, `Exercise`, `Lecture`, `MOOC`, `Notebook`, `Person`, `Publication`, `Specialisation`, `Startup`, `StudyPlan`, `Unit`, `Widget`. Each has `doc_type` + `doc_id` as a composite unique key and a 1-to-1 relation to `Profile`.
- **Link tables** — pre-materialized relationships between entity pairs. Naming convention: `Index_D_<Source>_L_<Target>_T_<Kind>`.
  - `_T_ORG` — organisational/structural links (degree_score).
  - `_T_SEM` — semantic links (semantic_score, row_score, row_rank).
  - Link subtypes include `Parent_to_Child`, `Child_to_Parent`, `Semantic`.
- **Ranking** — most link queries order by `row_rank ASC` and use `take`/`skip` pagination.
- **Visibility** — almost every query filters `profile.is_visible = true` on both sides of a relation.

### Website Database Schema (`prisma/website/schema.prisma`)

Stores auth and chat persistence:

- `user` — Better-Auth user record with EPFL fields: `given_name`, `family_name`, `gaspar`, `uniqueid`.
- `session`, `account`, `verification` — Better-Auth standard tables.
- `chat_conversation` — persisted chat messages with `chat_id`, `user_id`, `model`, `parent_message_id`, `messages` (JSON), `message_text`, `response`. Self-referential parent/children relation.

## Entity Types

Public entity types and their route prefixes:

| Type | Route | Notes |
| --- | --- | --- |
| person | `/person/:id` | People, EPFL affiliation, gender, courses, units, publications, etc. |
| concept | `/concept/:id` | Semantic concepts from the ontology graph. |
| course | `/course/:id` | Academic courses with latest academic year. |
| lecture | `/lecture/:id` | Video lectures, stream URLs, subtitles, restricted flag. |
| mooc | `/mooc/:id` | MOOCs with domain/language/level/platform enums. |
| notebook | `/notebook/:id` | Jupyter notebooks with type/language/repo/html URL. |
| publication | `/publication/:id` | Publications with year, publisher, authors. |
| unit | `/unit/:id` | EPFL units/labs, active/research flags. |
| startup | `/startup/:id` | Startups. |
| category | `/category/:id` | Hierarchical categories, depth field. |
| exercise | `/exercise/:id` | Exercises with difficulty, question type, PDF URLs. |
| widget | `/widget/:id` | Embedded quiz/widgets with platform/chapter/sequential IDs. |

Each entity page typically renders:

1. Main content (description, biography, markdown, sources).
2. Links sidebar with `<ErrorBoundary>` + `<Suspense>` wrapped relation sections (concepts, courses, persons, publications, etc.).

## Search & Elasticsearch

Files:

- `src/lib/elasticsearch.ts` — `Client` singleton pointing at `ELASTICSEARCH_NODE` with basic auth and `rejectUnauthorized: false`.
- `src/services/search/util.ts` — `search()` function. Builds a `function_score` query over `ELASTICSEARCH_INDEX`.
- `src/services/search/autocomplete.ts` — `/search` page logic; primary result + related items.
- `src/services/search/documents.ts` — document-search API used elsewhere.
- `src/services/search/typeOrder.ts` — defines per-source-type related-type limits and sort order.
- `src/schemas/search.ts` — Zod `Params`, `Item`, `Response`, `Type` enums.

Search behavior:

- Default search type is `"any"`.
- First fetches the top hit, extracts `links` as related items.
- Groups/limit related items by `typeOrder[sourceType][relatedType]`.
- Falls back to a broader `search()` if the limit is not reached.
- Autocomplete has a `fast` mode that skips `long_description.*` fields.
- Query scoring uses `degree_score_factor` multiplied into relevance.

## Chatbot

Files:

- `src/components/chatbot/index.tsx` — main chat UI component using `@ai-sdk/react` `useChat`.
- `src/contexts/chatbot.tsx` — chat open state + `?p=` / `?model=` query params via `nuqs`.
- `src/app/api/chat/route.ts` — streaming POST endpoint.
- `src/lib/chat.ts` — OpenAI-compatible provider configured with `CHATBOT_URL`.
- `src/services/chat.ts` — fetches available models from the chat backend and filters by `config.json` `chatbot.models`.
- `src/components/header/ChatbotLauncher.tsx` — floating launcher button.

Chat flow:

1. User must be authenticated; route returns 401 otherwise.
2. Request body contains `id` (chat id), `messages`, and optional `model`.
3. The server upserts the user message into `chat_conversation`.
4. `streamText()` calls the configured provider with `CHATBOT_API_KEY` header.
5. On finish the assistant text is saved to `response`.

## Authentication

Files:

- `src/lib/auth.ts` — `betterAuth` instance, Prisma adapter, Microsoft provider, PocketCampus plugin.
- `src/lib/authClient.ts` — React client.
- `src/lib/pocketcampus-sso.ts` — custom Better-Auth plugin verifying a JWT from Microsoft Entra ID and creating/linking users.
- `src/services/groups.ts` — EPFL API group membership check for `isUserAdmin`.

Auth flow:

- Microsoft SSO maps profile fields (`given_name`, `family_name`, `gaspar`, `uniqueid`) to the user record.
- `pocketCampusSso` endpoint `/api/auth/sso/pocketcampus` accepts a `?jwt=` param, verifies it against MS discovery keys, creates/links user, sets session cookie, redirects home.
- Admin role is determined by membership in the group configured in `config.json` `roles.admin` via `EPFL_API_URL` with service-account basic auth.

## Payload CMS

Files:

- `src/payload.config.ts`
- `src/payload/collections/{Alerts,Examples,FAQ,Users}.ts`
- `src/payload/access/isAdmin.ts`, `isAdminOrPublished.ts`
- `src/payload/components/LogoutButton.tsx`

Collections:

- `Users` — CMS admin users.
- `Alerts` — dismissible/global alerts shown in the header.
- `Examples` / `ExampleGroups` — chatbot prompt examples.
- `FAQ` — FAQ entries.

Payload uses SQLite (`PAYLOAD_DATABASE_URL`) and generates `src/payload-types.ts`.

## Key Components & Patterns

- `DocumentLayout` (`src/layouts/DocumentLayout.tsx`) — composite layout with `.Main` and `.Links` sub-components; wraps entity pages.
- `BaseLayout` — header (with search + chatbot), breadcrumbs, footer.
- `Section` — reusable titled section wrapper.
- `Content`, `Container` — layout primitives.
- `Link` — custom wrapper around Next.js link (locale aware).
- `Markdown` — renders markdown with `react-markdown`, KaTeX, highlight.js, GFM.
- `Search` — autocomplete search input using `downshift`.
- Entity components (`Person`, `Course`, `Lecture`, etc.) — presentational cards for relation lists.
- `OntologicalNeighbourhood` / `Ontology` — graph/ontology visualisation using `d3`.

## Localization Helpers

`src/utils/record.tsx`:

- `localeValue({ value, locale })` — pick `locale`, fall back to `en`, then `fr`.
- `localeRecord({ record, locale })` — pick a full locale record object with metadata.
- Entity schemas in `src/schemas/` flatten `profile` fields into the entity shape.

## Environment Variables

The project expects these environment variables (do not expose values):

- `HOST` — public base URL.
- `NEXT_PUBLIC_SENTRY_DSN`, `SENTRY_ORG`, `SENTRY_PROJECT`, `SENTRY_AUTH_TOKEN` — Sentry.
- `NEXT_PUBLIC_MATOMO_HOST`, `NEXT_PUBLIC_MATOMO_SITE_ID` — analytics.
- `MYSQL_URL_GRAPH` — MariaDB graph database.
- `MYSQL_URL_WEBSITE` — MariaDB website/auth/chat database.
- `PAYLOAD_DATABASE_URL` — SQLite URL for Payload.
- `ELASTICSEARCH_NODE`, `ELASTICSEARCH_AUTH_USERNAME`, `ELASTICSEARCH_AUTH_PASSWORD`, `ELASTICSEARCH_AUTH_CACERT` (optional), `ELASTICSEARCH_INDEX`.
- `CHATBOT_URL`, `CHATBOT_API_KEY` — chat backend.
- `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, `MICROSOFT_TENANT_ID` — Microsoft SSO.
- `POCKET_CAMPUS_CLIENT_ID`, `POCKET_CAMPUS_TENANT_ID` — PocketCampus SSO.
- `SERVICE_ACCOUNT_USERNAME`, `SERVICE_ACCOUNT_PASSWORD` — EPFL API basic auth.
- `EPFL_API_URL` — EPFL groups/people API.
- `SECRET` — Better-Auth/Payload secret.
- `NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION`, `NOINDEX`, `NEXT_TELEMETRY_DISABLED`.

## NPM Scripts

```bash
npm run dev              # Next.js dev server (Turbopack)
npm run build            # Production build
npm run start            # Start production server
npm run lint             # ESLint
npm run test             # Vitest
npm run prisma:generate:all
npm run prisma:db:pull:graph
npm run prisma:migrate:dev:website
npm run prisma:db:push:website
npm run payload
npm run payload:migrate
npm run payload:seed
```

## Configuration Files

- `config.json`:
  - `roles.admin` — admin group name.
  - `chatbot.defaultModel` / `chatbot.models` — allowed chat models.
  - `defaultLimit`, `searchResultsLimit`.
  - `sentry.tracesSampleRate` per environment.

- `next.config.ts`:
  - Page extensions include `md`, `mdx`.
  - Rewrites `/sitemap-:index.xml` to `/sitemap.xml/:index`.
  - Image remote patterns: `*.epfl.ch`, `api.kaltura.switch.ch`, `upload.wikimedia.org`.
  - Turbopack/Webpack alias: `micromark-extension-math` -> `micromark-extension-llm-math`.
  - Security headers (CSP frame-ancestors, HSTS, etc.).
  - Wrapped with Payload, next-intl, MDX, and Sentry.

## Coding Conventions

- TypeScript strict mode enabled.
- Path alias `@/*` maps to `src/*`.
- Prefer Server Components; use `"use client"` only for interactivity.
- Use `cache()` from `react` for expensive Prisma/ES calls.
- Always validate external input with Zod (`src/schemas/`).
- Use `next-intl` `getTranslations`/`useTranslations` for text; never hard-code UI strings.
- Use Tailwind utility classes; DaisyUI component classes (`btn`, `card`, `dropdown`, etc.).
- Entity relation sections should be wrapped in `<ErrorBoundary>` and `<Suspense>`.
- Prefer `const` arrow functions for components in relation sub-component files.

## Common Pitfalls

- The graph Prisma schema is auto-generated from an external database (`prisma db pull`). Do not hand-edit it; changes come from the upstream graph pipeline.
- The website Prisma schema is the source of truth for auth/chat and should be migrated normally.
- `Profile` contains nullable localized fields; always use `localeRecord`/`localeValue` and handle missing values.
- Link table queries must filter both `doc.profile.is_visible` and `link.profile.is_visible`.
- `better-auth` session calls often use `await headers()` inside Server Components.
- The chat provider is OpenAI-compatible, not necessarily OpenAI; base URL comes from `CHATBOT_URL`.
