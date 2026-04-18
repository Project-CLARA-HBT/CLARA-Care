# Stitch Prompts - CLARA Chat Redesign

Use all prompts in order. Keep labels and IDs unchanged.

## Prompt 00 - Global style baseline
Design a web app UI system for a medical AI workspace called CLARA Chat.
Requirements:
- calm, professional, high-trust medical SaaS tone
- dark + light theme ready
- strong readability and contrast
- no glassmorphism overload
- desktop first but mobile compatible
- include design tokens: spacing, radius, color roles, typography hierarchy
- use consistent component language for cards, tabs, chips, command palette, and side panels
- output should feel premium and minimal, not playful

## Prompt 01 - S01_Chat_Home_Desktop
Create desktop screen S01_Chat_Home_Desktop.
Layout:
- left workspace panel with view switcher (All, Chat, Notes, Discover, Shares)
- top conversation search input
- conversation list with metadata rows
- center/right main area with chat timeline
- bottom chat composer with mode chips and send button
- top action row for conversation tools
Data examples:
- conversation titles in Vietnamese
- medical/research style question previews

## Prompt 02 - S02_Chat_Home_Desktop_Telemetry_Open
Create screen S02 based on S01 with telemetry panel expanded on the right.
Telemetry panel must include:
- confidence score and level label
- source intel list
- logic flow steps (mini timeline)
- fallback messaging when no telemetry available

## Prompt 03 - S03_LeftPanel_Notes
Create screen S03 where left panel is in Notes view.
Include:
- note cards with title, tags, updated time
- create/edit note CTA
- pinned note indicator
- quick open from note to conversation

## Prompt 04 - S04_LeftPanel_Discover
Create screen S04 where left panel is in Discover view.
Include:
- suggestion groups
- searchable suggestions
- click suggestion to prefill composer

## Prompt 05 - S05_LeftPanel_Shares
Create screen S05 where left panel is in Shares view.
Include:
- share rows with status active/revoked
- copy link button
- open conversation from share
- button to open full Share Manager page

## Prompt 06 - S06_ScopeManager_Modal
Create modal screen S06 (overlay on top of S01).
Modal content:
- folder list
- create folder input
- rename/delete folder actions
- set folder filter
- apply folder to selected conversations
- clear filter action

## Prompt 07 - S07_CommandPalette_Modal
Create modal screen S07 (overlay on top of S01).
Include:
- command search input
- grouped command results
- shortcuts shown at right
- disabled commands style
- examples: new chat, export docx, export markdown, share, revoke share

## Prompt 08 - S08_ShareManagement_Page
Create dedicated page S08 for /chat/shares.
Include table:
- conversation id/title
- message count
- share status
- expires time
- public URL
- actions: copy/open/revoke
Also include top actions: back to chat, reload.

## Prompt 09 - S09_Chat_Home_Mobile_Default
Create mobile screen S09 (390x844) default state.
Include:
- compact top bar
- message timeline
- compact composer
- collapsed telemetry handle

## Prompt 10 - S10_Chat_Home_Mobile_Sidebar_Open
Create mobile screen S10 with slide-in sidebar open.
Sidebar includes:
- view switcher
- conversation list
- search/filter
- quick navigation items

## Prompt 11 - S11_Chat_Home_Mobile_Composer_Focus
Create mobile screen S11 with composer focused.
Include:
- larger input area
- visible mode chips
- send CTA priority
- keyboard-safe spacing

## Prompt 12 - S12_Chat_Home_Mobile_Telemetry_Open
Create mobile screen S12 with telemetry panel opened as bottom sheet.
Include:
- confidence
- source intel
- logic flow list
- close action

## Optional refinement prompt
Keep all screens visually coherent with one design system.
Improve information density for expert users while preserving clarity for normal users.
Prioritize fast scanning, low visual noise, and accessible contrast in dark mode.
