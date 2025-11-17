# Consideraciones de Seguridad

## Autenticación

La API utiliza JWT (JSON Web Tokens) para autenticar peticiones.
- El token se firma con `HS256` usando `SECRET_KEY`.
- El claim `sub` contiene el `username` del usuario.
- El token incluye `exp` (expiración) e `iat` (issued at).
- La expiración por defecto es de 24 horas.

## Contraseñas

- Las contraseñas NUNCA se almacenan en texto plano.
- Se utiliza `bcrypt` a través de `passlib` para el hashing.
- La política de contraseñas requiere mínimo 8 caracteres,
  al menos una mayúscula y un número.

## Rate Limiting

Se usa `slowapi` para limitar peticiones por IP:
- `POST /api/v1/auth/register`: 5 peticiones / hora.
- `POST /api/v1/auth/login`: 10 peticiones / minuto.
- Endpoints autenticados como `/api/v1/pokedex`: límites más altos (p.e. 100/min).
- Endpoints que llaman a PokeAPI (como `/api/v1/pokemon/search`): límites más restrictivos (30/min).

Esto protege frente a:
- Ataques de fuerza bruta de credenciales.
- Abuso de la API y costes excesivos de llamadas a PokeAPI.

Cuando se excede el límite, se devuelve `429 Too Many Requests`.

## CORS

Se ha configurado CORS para permitir únicamente orígenes conocidos:

- `http://localhost:3000`
- `http://localhost:5173`
- `https://tu-dominio.com`

Esto evita que aplicaciones web en dominios no autorizados consuman la API
desde el navegador.

## Variables de Entorno

Las siguientes variables sensibles se leen desde el entorno:

- `SECRET_KEY`
- `DATABASE_URL`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `ALGORITHM`

Nunca se sube un `.env` real al repositorio. Solo se incluye `.env.example`.

## Vulnerabilidades Conocidas y Mitigaciones

Se han tenido en cuenta las recomendaciones de OWASP API Security Top 10:

- **Broken Object Level Authorization (BOLA)**:
  - Todas las operaciones sobre recursos de usuario comprueban la propiedad
    (`owner_id`, `trainer_id`).

- **Broken Authentication**:
  - Uso de JWT con expiración.
  - Hash seguro de contraseñas.
  - Rate limiting en login y registro.

- **Excessive Data Exposure**:
  - Respuestas simplificadas de PokeAPI, mostrando solo campos necesarios.

- **Lack of Resources & Rate Limiting**:
  - `slowapi` configurado en endpoints críticos.

- **Security Misconfiguration**:
  - CORS restringido.
  - Logging estructurado de peticiones y errores.