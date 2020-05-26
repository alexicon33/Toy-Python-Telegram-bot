CREATE TABLE IF NOT EXISTS Network
(
	id text NOT NULL,
	point text NOT NULL,
	appeared timestamp NOT NULL,
	CONSTRAINT pk_Network PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS Moves
(
	id text NOT NULL,
	point_from text NOT NULL,
	point_to text NOT NULL,
	departure timestamp NOT NULL,
	arrival timestamp,
	CONSTRAINT pk_Moves PRIMARY KEY (id, departure),
	CONSTRAINT fk_Moves FOREIGN KEY (id) REFERENCES Network(id)
);