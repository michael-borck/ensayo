# ensayo

Generator for educational company simulation sites.

Ensayo scaffolds realistic, AI-generated content for simulated companies and builds vanilla HTML sites that deploy to GitHub Pages with zero build step.

## Architecture

```
ensayo init --brief brief.yaml --output ./my-simulation
```

Three concerns, one tool:

1. **Content generation** (`ensayo content`) — Uses AI to create rich employee backstories, support documents, and policies from a brief + archetypes + industry templates. Writes markdown with frontmatter into `content/`.

2. **Site building** (`ensayo build`) — Reads `site.yaml` + `content/` folder, applies a CSS theme, and produces a deployable vanilla HTML site. Picks up whatever content exists — AI-generated, hand-written, or a mix.

3. **Orchestration** (`ensayo init`) — Runs both: generates content from a brief, then builds the site. One command to get a draft simulation running.

## Install

```bash
pip install ensayo

# With AI content generation support
pip install ensayo[content]
```

## Quick start

```bash
# Generate a full draft simulation from a brief
ensayo init --brief brief.yaml --output ./pinnacle-events

# Or step by step:
ensayo content generate --brief brief.yaml --output ./pinnacle-events/content/
# ... review and edit content/ ...
ensayo build --config site.yaml --content ./pinnacle-events/content/ --output ./pinnacle-events/dist/
```

## Content workflow

```bash
# Add one employee to an existing simulation
ensayo content add-employee --name "Maria Santos" --role "Marketing Manager" --archetype marketing_manager

# Add a support document
ensayo content add-doc --type support --title "Emergency Procedures"

# Regenerate chatbot prompts after editing backstories
ensayo content prompts
```

## Site workflow

```bash
# Build the site (picks up whatever's in content/)
ensayo build

# Export booking API config from the built site
ensayo export-booking-config --output booking-employees.json
```

## Project structure

A simulation project looks like this:

```
my-simulation/
├── brief.yaml          # Content generation instructions (company, employees, scenario)
├── site.yaml           # Site build config (theme, branding, chatbot mode)
├── content/
│   ├── employees/      # Markdown with frontmatter — one file per employee
│   │   ├── sophie-anderson.md
│   │   └── rachel-martinez.md
│   ├── docs/
│   │   ├── support/    # Internal support documents
│   │   └── policies/   # Policy documents
│   ├── pages/          # Optional page overrides (about.md, services.md)
│   └── data/           # CSV data files (passed through as-is)
└── dist/               # Built site (push this to GitHub Pages)
```

## License

MIT
