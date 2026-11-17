-- MySQL 8 : extrait de mysqldump --no-data (schéma générique « bibliothèque »)
/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
DROP TABLE IF EXISTS `authors`;
CREATE TABLE `authors` (
  `id` int unsigned NOT NULL AUTO_INCREMENT COMMENT 'Identifiant',
  `name` varchar(100) NOT NULL,
  `country` char(2) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_country` (`country`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Auteurs';

DROP TABLE IF EXISTS `books`;
CREATE TABLE `books` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `isbn` varchar(13) NOT NULL,
  `title` varchar(255) NOT NULL,
  `kind` enum('novel','essay','poetry') NOT NULL DEFAULT 'novel',
  `tags` set('a','b') DEFAULT NULL,
  `in_stock` tinyint(1) NOT NULL DEFAULT '1',
  `pages` smallint DEFAULT NULL,
  `price` decimal(8,2) DEFAULT NULL,
  `published` year DEFAULT NULL,
  `price_ttc` decimal(8,2) GENERATED ALWAYS AS ((`price` * 1.2)) STORED,
  `author_id` int unsigned NOT NULL,
  `updated` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_isbn` (`isbn`),
  CONSTRAINT `fk_books_author` FOREIGN KEY (`author_id`) REFERENCES `authors` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `chk_pages` CHECK ((`pages` > 0))
) ENGINE=InnoDB;

CREATE TABLE `loans` (
  `id` int NOT NULL AUTO_INCREMENT,
  `book_id` bigint NOT NULL,
  `member_id` int NOT NULL,
  `loaned_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_loans_book` FOREIGN KEY (`book_id`) REFERENCES `books` (`id`),
  CONSTRAINT `fk_loans_member` FOREIGN KEY (`member_id`) REFERENCES `members` (`id`)
) ENGINE=InnoDB;
INSERT INTO `authors` VALUES (1,'Hugo','FR');
DELIMITER ;;
CREATE TRIGGER trg BEFORE INSERT ON books FOR EACH ROW BEGIN SET NEW.title = TRIM(NEW.title); END;;
DELIMITER ;
