---
name: i18n-ecriture-sure
description: Modifier des dictionnaires i18n (fr.json, en.json) ou tout JSON partagé sans le corrompre ni faire diverger les langues, par lecture avant écriture, fichier temporaire puis os.replace et contrôle de parité ; à utiliser dès qu'un agent ajoute ou corrige des textes d'interface, surtout quand plusieurs agents touchent le même fichier.
---

# i18n : écrire sans casser

## 1. Règle d'or
**Lire avant d'écrire.** Un autre agent a pu modifier le fichier depuis ta dernière lecture ; édite à partir de l'état actuel, jamais d'une copie de ta mémoire.

## 2. Écriture atomique (Python)
```python
import json, os, tempfile
def save(path, data):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=False)
        f.write("\n")
    os.replace(tmp, path)          # atomique : jamais de fichier à moitié écrit
```
Le fichier temporaire est dans le **même dossier** (sinon `os.replace` n'est pas atomique entre volumes). Conserver l'ordre des clés et l'indentation du fichier d'origine pour garder des diffs lisibles ; vérifier `git diff --stat` : seule la prose attendue change.

## 3. Parité et clés
- Chaque clé existe dans toutes les langues ; on ajoute les deux en même temps.
- Une clé existante ne change **ni de nom ni de sens** : les recettes, les ancres d'aide et les tests la référencent. Corriger le texte, pas la clé.
- Les ancres de documentation (`{#id}`) ne se traduisent pas (voir `doc-bilingue-captures`).
- Espaces réservés `{n}`, `{target}` : identiques dans les deux langues ; contrôler par script que l'ensemble des `{…}` est le même par clé.
- Pluriels : « constat(s) » est une dette ; préférer deux clés (singulier/pluriel) ou un vrai mécanisme de pluriel. Les formes courtes sont à traiter dans un lot dédié.
- Registre et tutoiement : suivre celui de l'appli (même verbe, même forme dans les deux langues).

## 4. Contrôle rapide
```bash
python - <<'PY'
import json,re
fr=json.load(open('frontend/src/i18n/fr.json',encoding='utf-8'));en=json.load(open('frontend/src/i18n/en.json',encoding='utf-8'))
print('manquantes en:',sorted(set(fr)-set(en))[:20]);print('manquantes fr:',sorted(set(en)-set(fr))[:20])
ph=lambda s:sorted(re.findall(r'\{\w+\}',s))
print('espaces réservés différents:',[k for k in fr if k in en and ph(fr[k])!=ph(en[k])][:20])
PY
```
(adapter si le dictionnaire est imbriqué). Puis `npm run build` et la recette anglaise (`english_scan.mjs` : cherche du français dans l'interface en anglais).

## 5. Pièges
- Deux agents qui réécrivent le même JSON en parallèle : le second écrase le premier sans erreur. Un fichier = un propriétaire par lot ; sinon passer par le propriétaire.
- Accents et guillemets typographiques : `ensure_ascii=False`, encodage UTF-8 explicite, jamais de `sed` multiligne sur du JSON.
- Texte généré côté serveur : il n'est pas dans le dictionnaire ; le documenter comme limite.
