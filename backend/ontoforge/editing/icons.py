"""Catalogue curaté d'icônes Font Awesome (version gratuite, style solid) pour la modélisation (L9)."""
from __future__ import annotations

import re
import unicodedata

ICON_RE = re.compile(r"^fa-[a-z0-9]+(-[a-z0-9]+)*$")

_RAW = [
    ('fa-user', 'Personne', 'Person', 'personne humain utilisateur individu person human user people'),
    ('fa-users', 'Groupe de personnes', 'People group', 'équipe groupe communauté team group community'),
    ('fa-user-tie', 'Employé / cadre', 'Employee', 'employé cadre manager contact employee manager business'),
    ('fa-user-shield', 'Agent / sécurité', 'Security agent', 'sécurité agent gendarme security agent guard'),
    ('fa-id-card', 'Identité', 'Identity', 'carte identité badge identity card badge'),
    ('fa-building', 'Organisation', 'Organization', 'entreprise société bâtiment organisation company organization building'),
    ('fa-landmark', 'Institution', 'Institution', 'institution administration banque musée institution government bank'),
    ('fa-industry', 'Usine / industrie', 'Factory', 'usine industrie production factory industry production'),
    ('fa-store', 'Magasin', 'Store', 'magasin commerce boutique shop store retail'),
    ('fa-house', 'Maison', 'House', 'maison habitation logement house home dwelling'),
    ('fa-hospital', 'Hôpital', 'Hospital', 'hôpital santé clinique hospital health clinic'),
    ('fa-school', 'École', 'School', 'école éducation school education'),
    ('fa-warehouse', 'Entrepôt', 'Warehouse', 'entrepôt stock dépôt warehouse stock depot'),
    ('fa-location-dot', 'Lieu', 'Place', 'lieu localisation adresse position place location address'),
    ('fa-map', 'Carte / zone', 'Map', 'carte zone territoire région map area region'),
    ('fa-globe', 'Pays / monde', 'Globe', 'pays monde géographie country world geography'),
    ('fa-route', 'Itinéraire', 'Route', 'itinéraire trajet chemin route path trip'),
    ('fa-car', 'Voiture', 'Car', 'voiture véhicule auto car vehicle automobile'),
    ('fa-truck', 'Camion', 'Truck', 'camion transport livraison truck transport delivery'),
    ('fa-motorcycle', 'Moto', 'Motorcycle', 'moto deux-roues motorcycle bike'),
    ('fa-bus', 'Bus', 'Bus', 'bus transport commun bus public transport'),
    ('fa-train', 'Train', 'Train', 'train rail train rail'),
    ('fa-plane', 'Avion', 'Plane', 'avion aérien vol plane aircraft flight'),
    ('fa-ship', 'Navire', 'Ship', 'bateau navire maritime ship boat maritime'),
    ('fa-bicycle', 'Vélo', 'Bicycle', 'vélo cycle bicycle bike'),
    ('fa-gas-pump', 'Carburant', 'Fuel', 'carburant essence station fuel gas station'),
    ('fa-gear', 'Composant / paramètre', 'Component', 'composant pièce paramètre configuration component part setting'),
    ('fa-gears', 'Système', 'System', 'système mécanisme machine system mechanism machine'),
    ('fa-wrench', 'Maintenance', 'Maintenance', 'maintenance réparation outil maintenance repair tool'),
    ('fa-screwdriver-wrench', 'Intervention', 'Intervention', 'intervention atelier outils intervention workshop tools'),
    ('fa-toolbox', 'Outillage', 'Toolbox', 'outillage kit toolbox kit'),
    ('fa-microchip', 'Équipement électronique', 'Electronic device', 'puce capteur électronique chip sensor electronics'),
    ('fa-server', 'Serveur', 'Server', 'serveur infrastructure server infrastructure'),
    ('fa-database', 'Base de données', 'Database', 'données base stockage data database storage'),
    ('fa-cloud', 'Cloud', 'Cloud', 'nuage cloud service cloud service'),
    ('fa-network-wired', 'Réseau', 'Network', 'réseau connexion network connection'),
    ('fa-laptop', 'Ordinateur', 'Computer', 'ordinateur poste computer laptop'),
    ('fa-mobile-screen', 'Mobile', 'Mobile', 'mobile téléphone smartphone mobile phone smartphone'),
    ('fa-code', 'Logiciel / code', 'Software', 'logiciel code application software code application'),
    ('fa-file', 'Fichier', 'File', 'fichier document file document'),
    ('fa-file-lines', 'Document', 'Document', 'document texte rapport document text report'),
    ('fa-file-contract', 'Contrat', 'Contract', 'contrat accord juridique contract agreement legal'),
    ('fa-file-invoice', 'Facture', 'Invoice', 'facture devis invoice quote'),
    ('fa-folder', 'Dossier', 'Folder', 'dossier répertoire folder directory'),
    ('fa-book', 'Livre / référentiel', 'Book', 'livre référentiel catalogue book reference catalog'),
    ('fa-clipboard-list', 'Liste / fiche', 'Checklist', 'liste fiche contrôle checklist form'),
    ('fa-tag', 'Étiquette / catégorie', 'Tag', 'étiquette catégorie type tag category type'),
    ('fa-tags', 'Catégories', 'Tags', 'catégories classification tags categories'),
    ('fa-cube', 'Objet / produit', 'Object', 'objet produit élément object product item'),
    ('fa-cubes', 'Lot / ensemble', 'Batch', 'lot ensemble assemblage batch assembly'),
    ('fa-box', 'Colis', 'Box', 'colis boîte emballage box package'),
    ('fa-boxes-stacked', 'Stock', 'Stock', 'stock inventaire stock inventory'),
    ('fa-barcode', 'Référence / code-barres', 'Barcode', 'référence code-barres identifiant barcode reference identifier'),
    ('fa-hashtag', 'Identifiant', 'Identifier', 'identifiant numéro identifier number'),
    ('fa-key', 'Clé', 'Key', 'clé accès key access'),
    ('fa-lock', 'Sécurité', 'Lock', 'sécurité verrou confidentiel security lock confidential'),
    ('fa-shield-halved', 'Protection', 'Shield', 'protection assurance protection insurance'),
    ('fa-triangle-exclamation', 'Alerte / risque', 'Alert', 'alerte risque anomalie alert risk anomaly'),
    ('fa-bug', 'Défaut', 'Defect', 'défaut bug panne defect bug failure'),
    ('fa-circle-check', 'Validé', 'Validated', 'validation conforme statut validated compliant status'),
    ('fa-flag', 'Statut / jalon', 'Flag', 'statut jalon drapeau status milestone flag'),
    ('fa-calendar', 'Date / événement', 'Calendar', 'date calendrier événement date calendar event'),
    ('fa-calendar-check', 'Rendez-vous', 'Appointment', 'rendez-vous planification appointment schedule'),
    ('fa-clock', 'Durée / horaire', 'Clock', 'durée horaire temps duration time schedule'),
    ('fa-hourglass-half', 'Période', 'Period', 'période délai period delay'),
    ('fa-euro-sign', 'Montant', 'Amount', 'montant prix euro coût amount price cost'),
    ('fa-credit-card', 'Paiement', 'Payment', 'paiement carte payment card'),
    ('fa-receipt', 'Transaction', 'Receipt', 'transaction reçu transaction receipt'),
    ('fa-chart-line', 'Indicateur', 'Metric', 'indicateur mesure statistique metric measure statistic'),
    ('fa-ruler', 'Mesure', 'Measure', 'mesure dimension measure dimension'),
    ('fa-temperature-half', 'Température', 'Temperature', 'température capteur temperature sensor'),
    ('fa-envelope', 'Message', 'Message', 'courriel message email email message'),
    ('fa-phone', 'Téléphone', 'Phone', 'téléphone appel contact phone call contact'),
    ('fa-comments', 'Échange', 'Conversation', 'échange discussion commentaire conversation discussion comment'),
    ('fa-graduation-cap', 'Formation', 'Training', 'formation diplôme compétence training degree skill'),
    ('fa-briefcase', 'Poste / mission', 'Job', 'poste mission emploi job assignment employment'),
    ('fa-handshake', 'Partenaire', 'Partner', 'partenaire client fournisseur partner customer supplier'),
    ('fa-cart-shopping', 'Commande', 'Order', 'commande achat panier order purchase cart'),
    ('fa-heart-pulse', 'Santé', 'Health', 'santé médical health medical'),
    ('fa-seedling', 'Plante', 'Plant', 'plante agriculture végétal plant agriculture'),
    ('fa-paw', 'Animal', 'Animal', 'animal faune animal pet'),
    ('fa-leaf', 'Environnement', 'Environment', 'environnement écologie environment ecology'),
    ('fa-bolt', 'Énergie', 'Energy', 'énergie électricité energy electricity'),
    ('fa-diagram-project', 'Processus', 'Process', 'processus flux projet process workflow project'),
    ('fa-sitemap', 'Hiérarchie', 'Hierarchy', 'hiérarchie structure arborescence hierarchy structure tree'),
    ('fa-puzzle-piece', 'Concept', 'Concept', 'concept module élément concept module piece'),
    ('fa-lightbulb', 'Idée', 'Idea', 'idée innovation idea innovation'),
    ('fa-star', 'Favori', 'Favorite', 'favori important favorite important'),
    ('fa-circle-question', 'Inconnu', 'Unknown', 'inconnu indéfini unknown undefined'),
]

ICONS: list[dict] = [
    {"id": i, "style": "solid", "label": {"fr": fr, "en": en}, "keywords": k.split()}
    for i, fr, en, k in _RAW
]
ICON_IDS = {i["id"] for i in ICONS}


def _norm(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def search(q: str | None = None) -> list[dict]:
    """Filtre par sous-chaîne (insensible à la casse et aux accents) sur id, libellés et mots-clés."""
    if not q or not q.strip():
        return ICONS
    needle = _norm(q.strip())
    return [i for i in ICONS if needle in _norm(" ".join([i["id"], i["label"]["fr"], i["label"]["en"], *i["keywords"]]))]
