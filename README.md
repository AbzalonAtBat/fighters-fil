# Fil Fighters

Agrégateur de presse **anglophone** sur les **Hokkaido Nippon-Ham Fighters** (NPB) :
les articles des sources anglophones dans un seul fil, avec le lien vers chaque
article original. Interface en français, articles en anglais — aucune traduction.

**Aucune API payante, aucune clé, aucun compte.**

## Site en ligne

Publié automatiquement par GitHub Pages toutes les 30 minutes.

## Sources

| Source | Type | État constaté (17/10/2026) |
|---|---|---|
| Bing News — 6 requêtes | presse anglophone (MLB Rumors, theScore, RotoWire, MSN, DAZN, note…) | actif |
| fighters.co.jp/en/news | site officiel du club, version anglaise | actif |

### Sources écartées, et pourquoi

Le projet fonctionne à l'identique de sa version MLB, mais le volume est bien plus
faible : **la couverture anglophone d'un club de NPB est rare**. Sondage mené le
17/10/2026 :

| Source | Verdict |
|---|---|
| Yakyu Cosmo (blog anglophone NPB) | flux valide mais **dernier article nov. 2025** |
| JapanBall | flux valide mais **dernier article oct. 2025** |
| NPB.jp version anglaise | **404** sur le flux de news |
| Reddit r/NPB | **403** — contrairement à r/phillies, le subreddit bloque |
| World Baseball | **404** |
| Japan Forward | flux vivant, mais **aucun article Fighters** (actualité générale) |

## Comment ça marche

```
GitHub Actions (cron 30 min)
   └─ collect.py   ── Bing News (6 requêtes) + site officiel via proxy
   └─ render.py    ── génère _site/index.html
   └─ déploiement GitHub Pages
```

Aucune base de données : le fil vit dans `data/items.json`.

## Notes techniques

- **Redirections Bing résolues** : les liens sont encapsulés dans
  `bing.com/news/apiclick.aspx`, mais Bing répond un vrai 302 vers l'éditeur —
  `resolve_bing()` le suit par HEAD. Google News a été écarté : ses jetons sont
  chiffrés et son endpoint de résolution refuse les IP de datacenter.
- **Site officiel via proxy gratuit** : pas de RSS exploitable (site Drupal), et
  l'accès direct est filtré par IP. La page de news est lue en markdown à travers
  `r.jina.ai`.
- **Fenêtre de 30 jours** et déduplication par similarité de titres.

## Droits

Titres et extraits appartiennent à leurs auteurs. Cette page n'affiche que des
amorces et renvoie systématiquement à la source. Aucun contenu de paywall.
