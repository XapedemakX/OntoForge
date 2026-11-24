# 11. Assistant Krakie {#assistant-krakie}

Krakie est l'assistant de conception d'OntoForge. Il converse en tenant compte de l'écran affiché et **propose** des actions (modifications de l'ontologie, ontologie partielle, contraintes de shapes, requête guidée, navigation, mise à jour de versions) ; il n'applique jamais rien lui-même (D-006). Il fonctionne avec un LLM configuré ou, sans LLM, avec des réponses déterministes.

Sources lues : `backend/ontoforge/assistant/agent.py`, `backend/ontoforge/assistant/service.py`, `backend/ontoforge/assistant/untrusted.py`, `backend/ontoforge/assistant/reasoning.py`, `backend/ontoforge/assistant/settings_help.py`, `backend/ontoforge/assistant/docdraft.py`, `backend/ontoforge/assistant/document.py`, `backend/ontoforge/assistant/docheur.py`, `backend/ontoforge/assistant/convert.py`, `backend/ontoforge/assistant/providers/`, `backend/ontoforge/api/assistant.py`, `backend/ontoforge/ratelimit.py`, `backend/ontoforge/settings/models.py`.

## Fichiers {#fichiers}

| Fichier | Responsabilité |
|---|---|
| `backend/ontoforge/assistant/agent.py` | assistant global conscient de l'écran : `run`, `build_actions`, `validate_ops` (essai à blanc), `validate_shape_patches`, `deterministic` (repli sans LLM), `Resolver` (retrouver une entité par nom ou libellé), `schema_compact` |
| `backend/ontoforge/assistant/service.py` | fonctions historiques : `draft` (brouillon depuis un texte), `propose_shapes`, `explain` (expliquer un constat), `chat`, `status` |
| `backend/ontoforge/assistant/untrusted.py` | `fence` (encadrer un contenu non fiable), `guard` (ajouter la règle de sécurité à l'invite système), `RULE` |
| `backend/ontoforge/assistant/reasoning.py` | intention « raisonne » : HermiT avant tout LLM (chapitre [05](05-conformite-owl-hermit.md#hermit-krakie)) |
| `backend/ontoforge/assistant/settings_help.py` | Krakie sur l'écran Paramètres, sans projet (D-L38-01) : instantané non sensible de la configuration, `redact` |
| `backend/ontoforge/assistant/document.py`, `docdraft.py`, `docheur.py` | amorcer une ontologie depuis un document (L25) : lecture et découpage, questions de compétence et brouillon par morceau, repli déterministe |
| `backend/ontoforge/assistant/convert.py` | `extract_json` (JSON dans une réponse de LLM), `to_onto` (proposition → `OntoModel`), `normalize_base` |
| `backend/ontoforge/assistant/providers/` | fournisseurs : `anthropic.py`, `openai_compat.py`, `ollama.py`, `mock.py` ; interface et HTTP communs dans `base.py` ; sélection dans `__init__.py` |
| `backend/ontoforge/api/assistant.py` | routes `/api/assistant/*` |

## Flux d'une conversation {#flux}

```mermaid
flowchart TD
  F[POST /api/assistant/chat {project_id?, messages, context, provider_id?, attachments}] --> S{project_id ?}
  S -- non, context.screen=settings --> SH[settings_help.run]
  S -- oui, context fourni --> R[agent.run]
  R --> L[langue de réponse : reply_lang du dernier message]
  L --> Z{intention « raisonne » ?}
  Z -- oui --> HZ[reasoning.answer : HermiT] --> BA
  Z -- non --> P{fournisseur réel configuré ?}
  P -- oui --> U[fence : contexte d'écran, schéma, pièces jointes ; guard : règle système]
  U --> C[provider.complete] --> J[extract_json → {reply, actions, warnings}]
  J --> BA[build_actions : validation de chaque action]
  P -- non --> D[deterministic : intentions simples] --> BA
  D -- rien --> CH[service.chat : mock ou aide]
  BA --> OUT[{reply, actions, proposal, warnings}]
```

Dans `backend/ontoforge/assistant/agent.py::run` :

- La conversation doit finir par un message de l'utilisateur (sinon 422) ; seuls les `MSG_LIMIT` (40) derniers messages sont gardés ; une pièce jointe est coupée à `ATT_LIMIT` (12 000 caractères).
- Un fournisseur est « réel » s'il est configuré et n'est pas `mock`. Sans fournisseur exploitable, pas d'erreur : repli déterministe.
- Une erreur du LLM devient un 502 avec un message sans secret. Une réponse qui n'est pas du JSON est renvoyée telle quelle comme texte, sans action.
- `build_actions` traite au plus 6 actions et **revalide** chacune côté serveur :

| Genre d'action | Validation |
|---|---|
| `ops` | `validate_ops` : chaque opération (60 au plus) est normalisée (IRI existantes retrouvées par `Resolver`, nouvelles entités sous l'IRI de base du projet), puis essayée sur une copie du projet (`editing/ops.py::apply_ops`) ; une opération qui échoue est retirée avec un avertissement |
| `proposal` | ontologie partielle convertie par `to_onto` ; jamais fusionnée ici |
| `shapes` | `validate_shape_patches` ; application par `POST /api/assistant/shapes/apply` (droit d'écriture, historique annulable) |
| `guided_query` | recalculée par `/query/nl` (chapitre [09](09-requetes.md#nl)) |
| `versions` | le serveur recalcule les versions recommandées (`standards.check`) : la demande du LLM n'est jamais appliquée telle quelle |
| `navigate`, `help` | écran pris dans une liste fermée |
| `settings_goto`, `settings_test` | écran Paramètres seulement, produits par `settings_help.run` (voir plus bas) ; le test est lancé par le front, sur clic du bouton « Tester la connexion » (`frontend/src/assistant-global/ActionCards.tsx::TestCard`), qui appelle `settingsApi.testProvider` ou `testEndpoint` ; le serveur ne l'exécute pas dans la réponse du chat |

Le front connaît ces neuf genres (`frontend/src/assistant-global/store.ts::ActionKind`).

L'application des actions `ops` se fait par la route d'édition (`POST /api/projects/{pid}/ops`, chapitre [13](13-projets-versions.md)), sur un clic de l'utilisateur.

## Contenus non fiables {#non-fiables}

Tout texte qui ne vient pas de la personne qui écrit (libellés et commentaires d'ontologie, documents, pièces jointes, constats, réponses d'endpoint) est encadré par `backend/ontoforge/assistant/untrusted.py::fence` dans un bloc `<donnees source="…">…</donnees>`. Une balise `donnees` présente dans le contenu est neutralisée : elle ne peut pas fermer le bloc. `guard` ajoute à chaque invite système une règle (prioritaire) qui interdit de suivre une instruction trouvée dans ces blocs. Le filet reste côté serveur : rien n'est appliqué sans clic, et chaque action est revalidée (SEC-17, OWASP LLM01).

## Fournisseurs LLM {#fournisseurs}

`backend/ontoforge/assistant/providers/__init__.py::get_provider` : `provider_id` explicite, sinon fournisseur par défaut des paramètres (`$ONTOFORGE_DATA/settings.json`, chapitre [12](12-comptes-partage-admin.md)) ; tant que ce fichier n'existe pas, variables d'environnement historiques (`ONTOFORGE_LLM_PROVIDER`, défaut `anthropic`).

| Genre | Classe | Point d'accès | Modèle par défaut | Configuré si |
|---|---|---|---|---|
| `anthropic` | `AnthropicProvider` | `https://api.anthropic.com/v1/messages` (ou `base_url` + `/v1/messages`), en-tête `anthropic-version: 2023-06-01` | `claude-sonnet-5-5` (`ONTOFORGE_LLM_MODEL`) | clé d'API |
| `openai_compat` | `OpenAICompatProvider` | `<base_url>/chat/completions` ; `response_format: json_object` si un schéma est demandé ; réglages non secrets (`reasoning_effort`, `temperature`, `top_p`) transmis | `gpt-4o` | `base_url` |
| `ollama` | `OllamaProvider` | serveur Ollama | `llama3.1` | `base_url` |
| `mock` | `MockProvider` | aucun réseau ; réponses déterministes du domaine automobile | — | toujours |

Toutes les requêtes passent par `backend/ontoforge/assistant/providers/base.py::post_json`, qui appelle `netguard.post` (contrôle des adresses sortantes, chapitre [16](16-securite.md)), applique le délai `ONTOFORGE_LLM_TIMEOUT` (120 s), traduit les erreurs HTTP en messages français (`http_error`) et masque les secrets dans le détail renvoyé (`_detail`). Une adresse refusée par `netguard` donne un message générique qui ne cite ni l'hôte ni l'adresse (L41-R1). La sortie structurée est demandée par le texte de l'invite (`schema_hint`) : aucun fournisseur n'utilise d'appel d'outil natif. D-006 citait aussi Bedrock : il n'y a pas de fournisseur Bedrock dans le code (`À CONFIRMER` : passage par un point d'accès compatible OpenAI).

Le fournisseur `mock` est le défaut des tests ; aucun test ne dépend d'une clé (D-021).

## Amorcer depuis un document {#document}

`backend/ontoforge/assistant/docdraft.py::draft_document` : document (`.txt`, `.md`, `.pdf` à texte natif lu par pypdf) découpé en morceaux (`document.py`, limites `ONTOFORGE_DOC_MAX_MB` 10, `ONTOFORGE_DOC_MAX_PAGES` 60, `ONTOFORGE_DOC_MAX_CHARS` 400 000, `ONTOFORGE_DOC_CHUNK_CHARS` 8 000) ; un appel « questions » puis un appel « brouillon » par morceau ; fusion des doublons ; contrôles déterministes (schéma strict, noms valides, IRI nouvelles, hiérarchie sans cycle, **extrait retrouvé dans le document**) ; lint W3C du brouillon (`lint(..., practices=False)`) ; couverture des questions. Avec un fournisseur hébergé, `confirm_hosted: true` est exigé (le document quitte la machine) ; avec `mock` ou `ollama`, rien ne sort. Sans LLM, `docheur.py` donne un brouillon approximatif, signalé comme tel. La proposition est revue élément par élément dans le front.

## Krakie sur l'écran Paramètres {#parametres}

`POST /api/assistant/chat` sans `project_id` n'est accepté que pour `context.screen = "settings"` (D-L38-01). `settings_help.run` n'envoie au LLM qu'un instantané **non sensible** de la configuration : ni clé, ni mot de passe, ni jeton, ni identifiant d'utilisateur, URL sans identifiants ni paramètres. Les messages et la réponse passent par `redact`. Actions propres : `settings_goto`, `settings_test`, `help`.

## Débit {#debit}

`backend/ontoforge/ratelimit.py` classe `/api/assistant/(chat|draft|shapes|explain|upload|shapes/apply|document/…)` et `/query/nl` dans la famille `assistant` : `ONTOFORGE_RATE_ASSISTANT_PER_MIN` (20 par minute, par adresse IP et par session), au-delà 429 avec `Retry-After`.

## Librairies {#librairies}

| Librairie | Version | Pourquoi |
|---|---|---|
| httpx | 0.28.1 | appels HTTP aux fournisseurs (via `netguard`) |
| pypdf | 7.0.0 | texte des PDF (amorçage depuis un document) |
| pydantic | 2.10.3 | configuration des fournisseurs, modèles de proposition |

Aucun SDK de fournisseur : les API sont appelées en HTTP JSON direct.

## Décisions {#decisions}

- D-006 : assistant à fournisseur configurable, toute proposition soumise à revue humaine.
- D-021 : `mock` par défaut dans les tests.
- D-L8-01 : clés d'API chiffrées dans les paramètres, jamais renvoyées.
- D-L38-01 : Krakie sur l'écran Paramètres.
- L39-secu (SEC-17) : contenus importés encadrés comme données non fiables.

## Pièges et limites {#pieges}

- Pas de flux continu : `complete` attend la réponse entière (délai 120 s par défaut).
- JSON par consigne : un modèle qui ne respecte pas le format donne une réponse texte sans action ; `extract_json` tolère du texte autour.
- Langue : la langue de la réponse suit le dernier message (`reply_lang`), pas le réglage de l'interface.
- Coût : chaque morceau d'un document fait deux appels ; `POST /api/assistant/document/estimate` estime avant de lancer.

## Comment ajouter… {#comment-ajouter}

**…un fournisseur.** Écrire une classe qui hérite de `Configured` dans `backend/ontoforge/assistant/providers/` (propriétés `model`, `configured`, méthode `complete(system, messages, max_tokens, json_schema)`), appeler le service par `post_json` (jamais `httpx` directement : on perdrait `netguard` et le masquage des secrets), l'enregistrer dans `PROVIDERS`, ajouter le genre à `Kind` de `backend/ontoforge/settings/models.py` et à l'écran Paramètres du front.

**…un genre d'action.** Ajouter la branche dans `build_actions` avec une validation serveur complète, la décrire dans l'invite `AGENT_SYSTEM`, et le rendu et l'application dans le front : type `ActionKind` (`frontend/src/assistant-global/store.ts`), carte (`frontend/src/assistant-global/ActionCards.tsx`), application sur clic (`frontend/src/assistant-global/run.ts`), chapitre [15](15-front.md). Une action ne doit jamais s'appliquer côté serveur sans un appel explicite de l'utilisateur.

**…une intention déterministe.** La reconnaître dans `deterministic` (ou un module dédié appelé avant le LLM, comme `reasoning.answer`) et renvoyer des actions brutes : elles passeront par `build_actions` comme celles du LLM.
