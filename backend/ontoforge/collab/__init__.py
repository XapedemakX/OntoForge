"""Projets nominatifs et partage collaboratif (L40, CONTRACTS §12).

- ``access``     : propriétaire, partages, version (rev), journal d'activité, présence, migration ;
- ``routes``     : table exhaustive route -> niveau d'accès (lecture, écriture, propriétaire) ;
- ``middleware`` : garde ASGI (cloisonnement, rôles, If-Match, ETag, journal) et réglages réservés aux administrateurs.
"""
