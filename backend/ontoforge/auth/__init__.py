"""Authentification par mot de passe pour une instance exposée (L27). Désactivée par défaut ; ``ONTOFORGE_AUTH=password`` l'active.

- ``config``     : lecture de l'environnement (comptes, durée, clé de session) ;
- ``passwords``  : hachage et vérification argon2 / bcrypt ;
- ``session``    : cookie signé (HMAC-SHA256, clé dérivée de ONTOFORGE_SECRET_KEY) avec jeton CSRF ;
- ``limiter``    : limitation des tentatives de connexion par IP, délai progressif ;
- ``middleware`` : protège ``/api/*`` (sauf ``/api/health`` et ``/api/auth/*``) et vérifie le CSRF ;
- ``python -m ontoforge.auth hash`` : produit le hachage d'un mot de passe.
"""
from .config import AuthConfig, AuthConfigError, load_config

__all__ = ["AuthConfig", "AuthConfigError", "load_config"]
