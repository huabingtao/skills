# Gemini Project Context: 弹壳特攻队攻略生成助手 (danke-strategy-skill)

## Directory Overview
This directory is a **Gemini CLI Skill Package** designed to generate professional game guides for "Survivor.io" (弹壳特攻队). It contains structured instructions, visual assets, and a knowledge base (references) for equipment, pets, and game mechanics.

## Key Files
- **`SKILL.md`**: The primary instructional document. It defines the "Persona" (弹壳呱呱), specific templates for articles, formatting standards for tables, and mandatory disclaimers.
- **`danke-strategy.skill`**: The binary skill definition file used by Gemini CLI to load this capability.
- **`assets/templates/`**: Contains `.docx` templates for different types of guides (event previews, standard guides).
- **`assets/img/`**: A library of game-related images (S/SS equipment, materials, etc.) used to enrich the generated content. `top.jpg` is the mandatory header image.
- **`references/`**: The project's knowledge base.
    - `docs/`: Original `.docx` files containing comprehensive guides, synthesis tables, and equipment introductions.
    - `*.md`: Extracted and condensed markdown files for quick reference (e.g., `equipment.md`, `cores.md`).

## Usage & Implementation Guidelines
When performing tasks within this project, adhere to the following:

1.  **Content Generation (The "Persona"):**
    - Always use the persona **"弹壳呱呱"**.
    - Follow the specific opening and closing remarks defined in `SKILL.md`.
    - Always include the mandatory **Disclaimer** at the end.

2.  **Referencing Data:**
    - Before generating or updating content, prioritize reading the files in `references/` and `references/docs/` to ensure accuracy regarding game stats and strategies.

3.  **Visual Standards:**
    - Mention or use `assets/img/top.jpg` as the primary header for articles.
    - Follow the **Table Beautification Standards** in `SKILL.md` (e.g., `#2C3E50` header background, zebra striping) when outputting or designing tables.

4.  **Template Adherence:**
    - For activity/event guides, follow the structure in `assets/templates/guide_template.docx`.

## Development Tasks
- **Updating Knowledge Base:** When game updates occur (new SS equipment, etc.), update the relevant files in `references/`.
- **Modifying Templates:** If the blogger's style changes, update `SKILL.md` and the templates in `assets/templates/`.
- **Adding Assets:** New equipment images should be added to `assets/img/` for future reference.
