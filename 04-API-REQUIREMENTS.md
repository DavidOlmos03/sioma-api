# Requisitos de API para Sincronización - IRIS

**Fecha**: 2025-01-24
**Versión**: 1.0
**Para**: Equipo Backend

## Resumen Ejecutivo

La aplicación móvil IRIS requiere un backend con autenticación de dispositivos y sincronización de registros de asistencia. El sistema debe soportar **múltiples dispositivos Android** (tablets, teléfonos) funcionando simultáneamente, cada uno con su propia identidad y token de autenticación.

**Características clave:**
- ✅ Funcionamiento 100% offline (sincronización opcional)
- ✅ Autenticación por dispositivo (no por usuario)
- ✅ Códigos de activación únicos de un solo uso
- ✅ Sincronización bidireccional de datos
- ✅ Manejo de conflictos y duplicados
- ✅ Desactivación remota de dispositivos

---

## 1. Autenticación y Registro de Dispositivos

### 1.1. Registro de Dispositivo

**Endpoint**: `POST /api/devices/register`

**Descripción**: Registra un nuevo dispositivo en el sistema usando un código de activación generado por un administrador.

**Request Body**:
```json
{
  "activation_code": "ACME-ABC123",
  "device_id": "550e8400-e29b-41d4-a716-446655440000",
  "device_name": "Tablet Entrada Principal",
  "device_model": "Samsung Galaxy Tab A7",
  "device_manufacturer": "Samsung",
  "android_version": "13"
}
```

**Response 201 Created**:
```json
{
  "success": true,
  "data": {
    "device_id": "550e8400-e29b-41d4-a716-446655440000",
    "tenant_id": "ACME",
    "device_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_expires_at": null,
    "is_active": true,
    "registered_at": 1706140800000
  }
}
```

**Errores**:
- `400 Bad Request`: Código inválido o ya usado
- `409 Conflict`: Dispositivo ya registrado
- `422 Unprocessable Entity`: Datos inválidos

**Validaciones**:
- El `activation_code` debe tener formato `TENANT-CODIGO` (ej: `ACME-ABC123`)
- El código debe existir en la base de datos del tenant correspondiente
- El código debe estar en estado "pending" (no usado)
- El `device_id` debe ser único (UUID v4)
- Después de usarse, el código debe marcarse como "used"
- El `tenant_id` se extrae automáticamente del código de activación

---

### 1.2. Renovación de Token

**Endpoint**: `POST /api/devices/refresh-token`

**Headers**:
```
Authorization: Bearer {device_token}
```

**Response 200 OK**:
```json
{
  "device_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_expires_at": 1706227200000
}
```

**Errores**:
- `401 Unauthorized`: Token inválido o expirado
- `403 Forbidden`: Dispositivo desactivado

---

### 1.3. Verificación de Estado del Dispositivo

**Endpoint**: `GET /api/devices/status`

**Headers**:
```
Authorization: Bearer {device_token}
```

**Response 200 OK**:
```json
{
  "device_id": "550e8400-e29b-41d4-a716-446655440000",
  "device_name": "Tablet Entrada Principal",
  "is_active": true,
  "last_sync_at": 1706140800000,
  "pending_records": 5
}
```

---

## 2. Sincronización de Registros de Asistencia

### 2.1. Subir Registros de Asistencia

**Endpoint**: `POST /api/attendance/sync`

**Headers**:
```
Authorization: Bearer {device_token}
X-Tenant-ID: ACME
Content-Type: application/json
```

**Nota**: El `tenant_id` debe coincidir con el tenant del token JWT. El servidor debe validar esta congruencia.

**Request Body**:
```json
{
  "records": [
    {
      "local_id": 123,
      "employee_id": "EMP001",
      "type": "ENTRY",
      "timestamp": 1706140800000,
      "confidence": 0.95,
      "liveness_passed": true,
      "device_id": "550e8400-e29b-41d4-a716-446655440000",
      "created_at": 1706140800000
    },
    {
      "local_id": 124,
      "employee_id": "EMP001",
      "type": "EXIT",
      "timestamp": 1706173200000,
      "confidence": 0.97,
      "liveness_passed": true,
      "device_id": "550e8400-e29b-41d4-a716-446655440000",
      "created_at": 1706173200000
    }
  ]
}
```

**Response 200 OK**:
```json
{
  "success": true,
  "synced_count": 2,
  "synced_records": [
    {
      "local_id": 123,
      "server_id": 5001,
      "synced_at": 1706180000000
    },
    {
      "local_id": 124,
      "server_id": 5002,
      "synced_at": 1706180000000
    }
  ],
  "conflicts": [],
  "errors": []
}
```

**Response con Conflictos**:
```json
{
  "success": true,
  "synced_count": 1,
  "synced_records": [
    {
      "local_id": 123,
      "server_id": 5001,
      "synced_at": 1706180000000
    }
  ],
  "conflicts": [
    {
      "local_id": 124,
      "reason": "DUPLICATE_TIMESTAMP",
      "message": "Ya existe un registro para este empleado en este timestamp",
      "existing_record": {
        "server_id": 4999,
        "timestamp": 1706173200000,
        "device_id": "other-device-uuid"
      }
    }
  ],
  "errors": []
}
```

**Errores**:
- `401 Unauthorized`: Token inválido
- `403 Forbidden`: Dispositivo desactivado
- `413 Payload Too Large`: Demasiados registros (máx 100 por request)
- `422 Unprocessable Entity`: Datos inválidos

**Lógica de Duplicados**:
- Si existe un registro del mismo empleado con timestamp dentro de ±30 segundos: **RECHAZAR como duplicado**
- El dispositivo debe marcar el registro local como sincronizado SOLO si `synced_records` lo incluye
- Los registros con conflictos NO deben marcarse como sincronizados

---

### 2.2. Descargar Actualizaciones

**Endpoint**: `GET /api/attendance/updates?since={timestamp}`

**Headers**:
```
Authorization: Bearer {device_token}
```

**Query Parameters**:
- `since` (required): Timestamp en milisegundos desde el cual obtener cambios

**Response 200 OK**:
```json
{
  "updates": [
    {
      "server_id": 5003,
      "employee_id": "EMP002",
      "type": "ENTRY",
      "timestamp": 1706184400000,
      "device_id": "other-device-uuid",
      "action": "CREATED"
    },
    {
      "server_id": 5001,
      "employee_id": "EMP001",
      "type": "ENTRY",
      "timestamp": 1706140800000,
      "device_id": "550e8400-e29b-41d4-a716-446655440000",
      "action": "DELETED",
      "deleted_by_admin_id": 42,
      "deletion_reason": "Registro erróneo"
    }
  ],
  "last_sync_timestamp": 1706185000000
}
```

**Nota**: Este endpoint permite que dispositivos se enteren de registros creados en otros dispositivos y de eliminaciones administrativas.

---

## 3. Sincronización de Auditoría

### 3.1. Subir Registros de Auditoría

**Endpoint**: `POST /api/audit/sync`

**Headers**:
```
Authorization: Bearer {device_token}
Content-Type: application/json
```

**Request Body**:
```json
{
  "audits": [
    {
      "local_id": 501,
      "attendance_id": 123,
      "action": "CANCELLED_BY_USER",
      "employee_id_detected": "EMP001",
      "employee_id_actual": null,
      "performed_by_user_id": null,
      "reason": "Usuario rechazó identificación",
      "metadata": "{\"confidence\":0.82}",
      "timestamp": 1706140900000
    }
  ]
}
```

**Response 200 OK**:
```json
{
  "success": true,
  "synced_count": 1,
  "synced_audits": [
    {
      "local_id": 501,
      "server_id": 7001,
      "synced_at": 1706180000000
    }
  ]
}
```

---

## 4. Panel de Administración

### 4.1. Generar Código de Activación

**Endpoint**: `POST /api/admin/activation-codes`

**Headers**:
```
Authorization: Bearer {admin_token}
Content-Type: application/json
```

**Request Body**:
```json
{
  "code": "ACME-ABC123",
  "description": "Tablet para entrada principal - Acme Corp",
  "expires_at": 1706227200000
}
```

**Response 201 Created**:
```json
{
  "code": "ACME-ABC123",
  "tenant_id": "ACME",
  "status": "pending",
  "created_at": 1706140800000,
  "expires_at": 1706227200000,
  "description": "Tablet para entrada principal - Acme Corp"
}
```

**Nota**: El admin debe estar autenticado y pertenecer al tenant `ACME` para generar códigos con ese prefijo.

---

### 4.2. Listar Dispositivos Activos

**Endpoint**: `GET /api/admin/devices`

**Response 200 OK**:
```json
{
  "devices": [
    {
      "device_id": "550e8400-e29b-41d4-a716-446655440000",
      "device_name": "Tablet Entrada Principal",
      "device_model": "Samsung Galaxy Tab A7",
      "registered_at": 1706140800000,
      "last_sync_at": 1706180000000,
      "is_active": true,
      "pending_records": 0
    }
  ]
}
```

---

### 4.3. Desactivar Dispositivo

**Endpoint**: `PUT /api/admin/devices/{device_id}/deactivate`

**Request Body**:
```json
{
  "reason": "Dispositivo extraviado"
}
```

**Response 200 OK**:
```json
{
  "success": true,
  "message": "Dispositivo desactivado correctamente"
}
```

**Efecto**:
- El dispositivo ya no podrá sincronizar
- Intentos de sincronización devolverán `403 Forbidden`
- Los datos locales permanecen intactos

---

## 5. Seguridad

### 5.1. Autenticación JWT

**Estructura del Token**:
```json
{
  "tenant_id": "ACME",
  "device_id": "550e8400-e29b-41d4-a716-446655440000",
  "iat": 1706140800,
  "exp": null
}
```

**Importante**: El `tenant_id` en el token JWT es la fuente de verdad. El header `X-Tenant-ID` debe coincidir para validación adicional.

**Notas**:
- Los tokens NO expiran por defecto (`exp: null`)
- Si se implementa expiración, usar endpoint de renovación
- Algoritmo recomendado: **HS256** o **RS256**

---

### 5.2. Rate Limiting

**Límites recomendados**:
- `/api/devices/register`: 5 intentos por IP por hora
- `/api/attendance/sync`: 100 requests por dispositivo por hora
- `/api/audit/sync`: 50 requests por dispositivo por hora

---

### 5.3. Validación de Datos

**Reglas críticas**:
1. **employee_id**: Debe existir en la tabla de empleados
2. **timestamp**: No puede ser futuro (max: now + 5 minutos de tolerancia)
3. **confidence**: Rango [0.0, 1.0]
4. **type**: Solo "ENTRY" o "EXIT"
5. **device_id**: Debe coincidir con el token JWT

---

## 6. Códigos de Estado HTTP

| Código | Significado | Cuándo Usar |
|--------|-------------|-------------|
| 200 | OK | Sincronización exitosa |
| 201 | Created | Dispositivo registrado |
| 400 | Bad Request | Código de activación inválido |
| 401 | Unauthorized | Token inválido o expirado |
| 403 | Forbidden | Dispositivo desactivado |
| 409 | Conflict | Dispositivo ya registrado |
| 413 | Payload Too Large | Demasiados registros |
| 422 | Unprocessable Entity | Validación de datos fallida |
| 429 | Too Many Requests | Rate limit excedido |
| 500 | Internal Server Error | Error del servidor |

---

## 7. Flujo Completo

### 7.1. Primera Vez (Registro)

```
1. Admin de "Acme Corp" genera código "ACME-ABC123" desde panel web
2. Usuario ingresa código "ACME-ABC123" en app móvil
3. App parsea código → tenant: "ACME", code: "ABC123"
4. App envía POST /api/devices/register con activation_code completo
5. Servidor valida código, extrae tenant, verifica que exista y esté disponible
6. Servidor genera token JWT con tenant_id: "ACME" embebido
7. App guarda token y tenant_id en base de datos local
8. App está lista para sincronizar con tenant "ACME"
```

### 7.2. Sincronización Normal

```
1. Usuario registra asistencia (funciona offline)
2. WorkManager ejecuta cada 15 min
3. App verifica si device está registrado
4. App obtiene registros no sincronizados
5. App envía POST /api/attendance/sync con token
6. Servidor valida token y procesa registros
7. Servidor devuelve IDs sincronizados
8. App marca registros como sincronizados
9. App actualiza timestamp de última sync
```

### 7.3. Dispositivo Desactivado

```
1. Admin desactiva dispositivo desde panel
2. App intenta sincronizar
3. Servidor responde 403 Forbidden
4. App actualiza estado: "Dispositivo desactivado"
5. App sigue funcionando en modo local
```

---

## 8. Modelo de Datos en DynamoDB

### 8.1. Tabla: DeviceRegistrations

**Partition Key**: `device_id` (String)
**Sort Key**: N/A

**Índices Secundarios Globales (GSI)**:
- **GSI1**: `tenant_id` (PK) + `registered_at` (SK)
  - Para listar dispositivos por tenant
- **GSI2**: `activation_code` (PK)
  - Para verificar códigos usados

**Atributos**:
```json
{
  "device_id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "ACME",
  "device_name": "Tablet Entrada Principal",
  "device_model": "Samsung Galaxy Tab A7",
  "device_manufacturer": "Samsung",
  "android_version": "13",
  "activation_code": "ACME-ABC123",
  "device_token": "eyJhbGc...",
  "is_active": true,
  "registered_at": 1706140800000,
  "last_sync_at": 1706180000000,
  "deactivated_at": null,
  "deactivation_reason": null
}
```

**Patrones de Acceso**:
1. Obtener dispositivo por ID: `GetItem(device_id)`
2. Listar dispositivos de un tenant: `Query(GSI1, tenant_id)`
3. Verificar código de activación: `Query(GSI2, activation_code)`

---

### 8.2. Tabla: ActivationCodes

**Partition Key**: `code` (String)
**Sort Key**: N/A

**Índices Secundarios Globales (GSI)**:
- **GSI1**: `tenant_id` (PK) + `created_at` (SK)
  - Para listar códigos por tenant
- **GSI2**: `tenant_id` (PK) + `status` (SK)
  - Para filtrar códigos pendientes/usados

**Atributos**:
```json
{
  "code": "ACME-ABC123",
  "tenant_id": "ACME",
  "status": "pending",
  "description": "Tablet para entrada principal",
  "created_by_admin_id": "admin-123",
  "created_at": 1706140800000,
  "expires_at": 1706227200000,
  "used_at": null,
  "used_by_device_id": null
}
```

**TTL**: Configurar TTL en `expires_at` para auto-eliminación de códigos expirados.

**Patrones de Acceso**:
1. Validar código: `GetItem(code)`
2. Listar códigos de un tenant: `Query(GSI1, tenant_id)`
3. Listar códigos pendientes: `Query(GSI2, tenant_id + status='pending')`

---

### 8.3. Tabla: AttendanceRecords

**Partition Key**: `tenant_id#employee_id` (String)
**Sort Key**: `timestamp` (Number)

**Formato de PK**: `ACME#EMP001`
Esto permite agrupar todos los registros de un empleado en la misma partición.

**Índices Secundarios Globales (GSI)**:
- **GSI1**: `tenant_id` (PK) + `timestamp` (SK)
  - Para obtener todos los registros de un tenant ordenados por fecha
- **GSI2**: `device_id` (PK) + `timestamp` (SK)
  - Para obtener registros de un dispositivo específico
- **GSI3**: `tenant_id#sync_status` (PK) + `timestamp` (SK)
  - Para obtener registros pendientes de sincronización

**Atributos**:
```json
{
  "tenant_id#employee_id": "ACME#EMP001",
  "timestamp": 1706140800000,
  "record_id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "ACME",
  "employee_id": "EMP001",
  "type": "ENTRY",
  "confidence": 0.95,
  "liveness_passed": true,
  "device_id": "550e8400-e29b-41d4-a716-446655440000",
  "local_id": 123,
  "created_at": 1706140800000,
  "synced_at": 1706180000000,
  "deleted_at": null,
  "deleted_by_admin_id": null,
  "deletion_reason": null,
  "sync_status": "synced"
}
```

**Atributo Calculado para GSI3**:
```javascript
sync_status = synced_at ? "synced" : "pending"
tenant_id#sync_status = `${tenant_id}#${sync_status}` // "ACME#pending"
```

**Patrones de Acceso**:
1. Registros de un empleado: `Query(PK = "ACME#EMP001")`
2. Registros de un empleado en rango de fecha: `Query(PK = "ACME#EMP001", SK BETWEEN start AND end)`
3. Todos los registros de un tenant: `Query(GSI1, tenant_id = "ACME")`
4. Registros de un dispositivo: `Query(GSI2, device_id)`
5. Registros pendientes de sync: `Query(GSI3, tenant_id#sync_status = "ACME#pending")`

**Detección de Duplicados**:
```javascript
// Antes de insertar, verificar:
Query(
  PK = "ACME#EMP001",
  SK BETWEEN (timestamp - 30000) AND (timestamp + 30000)
)
// Si retorna items, es duplicado
```

---

### 8.4. Tabla: AuditLogs (Opcional)

**Partition Key**: `tenant_id#attendance_id` (String)
**Sort Key**: `timestamp` (Number)

**Atributos**:
```json
{
  "tenant_id#attendance_id": "ACME#550e8400-...",
  "timestamp": 1706140900000,
  "audit_id": "audit-uuid",
  "tenant_id": "ACME",
  "attendance_id": "550e8400-...",
  "action": "CANCELLED_BY_USER",
  "employee_id_detected": "EMP001",
  "employee_id_actual": null,
  "performed_by_user_id": null,
  "reason": "Usuario rechazó identificación",
  "metadata": "{\"confidence\":0.82}",
  "device_id": "device-uuid"
}
```

---

## 8.5. Consideraciones Importantes de DynamoDB

### **Multi-Tenancy y Aislamiento**

**CRÍTICO**: Nunca usar Scan operations. Siempre usar Query con `tenant_id`:

```javascript
// ❌ MAL - Expone datos de todos los tenants
const result = await dynamodb.scan({
  TableName: 'AttendanceRecords'
}).promise();

// ✅ BIEN - Solo datos del tenant
const result = await dynamodb.query({
  TableName: 'AttendanceRecords',
  IndexName: 'GSI1',
  KeyConditionExpression: 'tenant_id = :tenant',
  ExpressionAttributeValues: {
    ':tenant': 'ACME'
  }
}).promise();
```

### **Capacidad y Costos**

**Provisioned Capacity** (recomendado para inicio):
- DeviceRegistrations: 5 RCU / 5 WCU
- ActivationCodes: 1 RCU / 2 WCU
- AttendanceRecords: 10 RCU / 10 WCU (puede escalar según uso)

**On-Demand** (para producción con tráfico variable):
- Auto-scaling según demanda
- Más costoso pero sin administración

### **Hot Partitions**

Si un empleado tiene muchísimos registros, puede crear hot partition.

**Solución**: Agregar sufijo de mes al PK:
```
PK = "ACME#EMP001#2025-01"
```

Esto distribuye datos en múltiples particiones.

### **Backup y Recuperación**

- Habilitar **Point-in-Time Recovery (PITR)**
- Backup diario automático
- Retention: mínimo 7 días

### **Encriptación**

- Usar AWS KMS encryption at rest
- Todas las tablas deben estar encriptadas
- Considerar Customer Managed Keys (CMK) para mayor control

---

## 9. Preguntas Frecuentes

**Q: ¿Cómo funciona el multi-tenancy?**
A: Cada organización tiene su propio `tenant_id`. Los códigos de activación tienen formato `TENANT-CODIGO`. El tenant se embebe en el JWT y todas las consultas filtran por tenant para aislar datos.

**Q: ¿Pueden dos organizaciones usar el mismo código de activación?**
A: NO. Los códigos son globalmente únicos: `ACME-ABC123` y `TECH-ABC123` son diferentes códigos.

**Q: ¿Qué pasa si dos dispositivos registran al mismo empleado casi simultáneamente?**
A: El servidor debe detectar duplicados (timestamp ±30s **del mismo tenant**) y rechazar el segundo. El dispositivo rechazado debe mostrar el conflicto al usuario.

**Q: ¿Los tokens expiran?**
A: Por defecto NO. Si se requiere expiración, implementar endpoint de renovación.

**Q: ¿Qué pasa si el dispositivo se desactiva?**
A: Solo afecta sincronización. La app sigue funcionando en modo local.

**Q: ¿Cómo se manejan eliminaciones de registros?**
A: El admin elimina desde el panel → se marca como `deleted_at` → próxima sincronización descarga el cambio → app elimina registro local.

**Q: ¿Se pueden sincronizar embeddings faciales?**
A: NO por razones de tamaño y privacidad. Solo se sincronizan registros de asistencia.

**Q: ¿Un dispositivo puede cambiar de tenant?**
A: NO. El tenant se define al momento del registro y es permanente. Para cambiar de tenant, debe desregistrarse y registrarse nuevamente con un código del nuevo tenant.

---

## 10. Notas de Implementación

1. **Batch Size**: Limitar a 100 registros por request
2. **Retry Logic**: La app reintenta automáticamente con backoff exponencial
3. **Idempotencia**: El servidor debe manejar envíos duplicados (mismo `local_id`)
4. **Timestamps**: Siempre en milisegundos (Unix epoch)
5. **UTF-8**: Todos los strings en UTF-8
6. **Timezone**: Timestamps en UTC en servidor, conversión local en app

---

## 11. Contacto

Para preguntas sobre esta especificación, contactar al equipo de desarrollo móvil.

**Versión del Documento**: 1.0
**Última Actualización**: 2025-01-24
