-- PostgreSQL 16 : extrait de pg_dump --schema-only (schéma générique « boutique »)
SET statement_timeout = 0;
SET client_encoding = 'UTF8';
SELECT pg_catalog.set_config('search_path', '', false);
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE TYPE public.order_status AS ENUM ('pending', 'paid', 'shipped');
CREATE DOMAIN public.email AS text CHECK (VALUE ~ '^.+@.+$');

CREATE TABLE public.customers (
    customer_id integer NOT NULL,
    email public.email NOT NULL,
    full_name character varying(120) NOT NULL,
    birth_date date,
    loyalty smallint DEFAULT 0,
    segment text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT customers_segment_check CHECK ((segment = ANY (ARRAY['retail'::text, 'pro'::text]))),
    CONSTRAINT customers_loyalty_check CHECK (((loyalty >= 0) AND (loyalty <= 100)))
);
COMMENT ON TABLE public.customers IS 'Personnes qui achètent';
COMMENT ON COLUMN public.customers.email IS 'Adresse de contact';

CREATE TABLE public.orders (
    order_id bigint GENERATED ALWAYS AS IDENTITY,
    customer_id integer NOT NULL,
    status public.order_status DEFAULT 'pending'::public.order_status NOT NULL,
    total numeric(12,2),
    notes text[],
    payload jsonb,
    placed interval
);

CREATE TABLE public.products (
    sku character varying(20) PRIMARY KEY,
    label text NOT NULL,
    price double precision
);

CREATE TABLE public.order_lines (
    order_id bigint NOT NULL,
    sku character varying(20) NOT NULL,
    quantity integer NOT NULL CHECK (quantity > 0),
    PRIMARY KEY (order_id, sku),
    FOREIGN KEY (order_id) REFERENCES public.orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (sku) REFERENCES public.products(sku)
);

CREATE TABLE public.product_tags (
    sku character varying(20) NOT NULL REFERENCES public.products(sku),
    tag_id integer NOT NULL,
    PRIMARY KEY (sku, tag_id)
);
CREATE TABLE public.tags (tag_id integer PRIMARY KEY, name text UNIQUE NOT NULL);
ALTER TABLE ONLY public.product_tags ADD CONSTRAINT product_tags_tag_fk FOREIGN KEY (tag_id) REFERENCES public.tags(tag_id);

CREATE TABLE public.vip_customers (customer_id integer PRIMARY KEY REFERENCES public.customers(customer_id), since date);

ALTER TABLE ONLY public.customers ADD CONSTRAINT customers_pkey PRIMARY KEY (customer_id);
ALTER TABLE ONLY public.orders ADD CONSTRAINT orders_pkey PRIMARY KEY (order_id);
ALTER TABLE ONLY public.orders ADD CONSTRAINT orders_customer_fk FOREIGN KEY (customer_id) REFERENCES public.customers(customer_id);
CREATE UNIQUE INDEX customers_email_key ON public.customers USING btree (email);
CREATE INDEX orders_status_idx ON public.orders (status);
CREATE VIEW public.paid AS SELECT * FROM public.orders WHERE status = 'paid';
CREATE FUNCTION public.f() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN CREATE TABLE evil (x int); RETURN NEW; END $$;
INSERT INTO public.tags VALUES (1, 'a');
GRANT SELECT ON public.tags TO PUBLIC;
