Tarea: Análisis y documentación técnica integral del proyecto web

En el proyecto que tienes asignado, realiza un análisis exhaustivo de toda la estructura y el código fuente existente. A partir de ese análisis, crea un nuevo archivo llamado DOCUMENTACION_PROYECTO.md en la raíz del proyecto.

El objetivo es generar una documentación técnica completa, rigurosa, explicativa y actualizada que permita a cualquier desarrollador comprender cómo funciona el proyecto, cómo está organizado, cuáles son sus dependencias y cómo se relacionan sus diferentes componentes.

IMPORTANTE: Antes de redactar el documento, inspecciona el proyecto y analiza los archivos relevantes. No te limites a revisar los archivos principales. Debes identificar las conexiones, dependencias, configuraciones y flujos de funcionamiento reales.

1. Descripción general del proyecto
Propósito y objetivo principal del sistema.
Problema que busca resolver.
Funcionalidades principales implementadas.
Tecnologías, lenguajes, frameworks y herramientas utilizadas.
Estado actual del proyecto y nivel de implementación.
2. Arquitectura y estructura del proyecto
Explica la arquitectura general de la aplicación.
Describe la organización de carpetas y subcarpetas.
Explica la responsabilidad de cada directorio.
Identifica los archivos principales y explica para qué sirven.
Describe cómo se relacionan los diferentes módulos.
Identifica los patrones de diseño o arquitectónicos utilizados, si existen.

Incluye un árbol de directorios representativo y comentado, evitando listar archivos irrelevantes como dependencias instaladas, archivos temporales o contenido generado automáticamente.

3. Tecnologías y dependencias
Identifica todas las tecnologías utilizadas en frontend y backend.
Documenta los frameworks, librerías y paquetes principales.
Explica para qué se utiliza cada dependencia importante.
Identifica las versiones cuando estén disponibles.
Explica cómo se gestionan las dependencias.
4. Frontend
Describe la estructura del frontend.
Explica las páginas, vistas, componentes y módulos principales.
Documenta el sistema de navegación y las rutas.
Explica cómo se gestiona el estado de la aplicación.
Describe cómo se comunica el frontend con el backend.
Identifica los formularios, validaciones y mecanismos de interacción relevantes.
5. Backend y lógica de negocio
Describe la arquitectura del backend.
Identifica controladores, servicios, modelos, repositorios y otros componentes existentes.
Explica las responsabilidades de cada módulo.
Documenta las rutas o endpoints disponibles.
Explica los métodos HTTP, parámetros, validaciones y respuestas.
Describe los principales procesos y reglas de negocio.
Documenta el flujo de ejecución de las operaciones más importantes.
6. Base de datos
Identifica el motor de base de datos utilizado.
Explica cómo se establece la conexión.
Documenta las tablas, colecciones o entidades existentes.
Describe los campos importantes, tipos de datos y claves.
Explica las relaciones entre las entidades.
Identifica claves primarias, foráneas, índices y restricciones cuando existan.
Documenta migraciones, esquemas, modelos y mecanismos de acceso a datos.
Explica qué operaciones realiza el sistema sobre la base de datos.

Incluye diagramas entidad-relación en Mermaid cuando la información disponible permita construirlos correctamente.

7. Conexiones e integraciones

Identifica y documenta todas las conexiones entre los componentes del sistema:

Frontend y backend.
Backend y base de datos.
APIs internas y externas.
Servicios de terceros.
Sistemas de autenticación y autorización.
Almacenamiento de archivos.
Servicios adicionales utilizados por el proyecto.

Para cada conexión explica:

Qué componentes se comunican.
Qué tecnología o protocolo utilizan.
Qué información intercambian.
Cómo se establece la comunicación.
En qué archivos se encuentra implementada.
8. Autenticación y seguridad
Explica el sistema de autenticación implementado.
Describe los mecanismos de autorización y control de acceso.
Documenta la gestión de sesiones, tokens y permisos.
Identifica las validaciones y medidas de seguridad existentes.
Explica cómo se gestionan las variables de entorno y credenciales sin revelar valores sensibles.
Señala posibles riesgos o aspectos de seguridad que requieran atención.
9. Configuración e instalación

Documenta cómo preparar el entorno de desarrollo:

Requisitos previos.
Instalación de dependencias.
Configuración de variables de entorno.
Configuración de la base de datos.
Ejecución de migraciones o inicialización de datos.
Comandos para ejecutar el frontend y backend.
Comandos para ejecutar pruebas y compilaciones.
Configuración necesaria para producción, si está definida.

Incluye los comandos reales identificados en los archivos de configuración del proyecto.

10. Flujos principales del sistema

Describe paso a paso los flujos funcionales más importantes.

Por ejemplo:

Inicio de sesión.
Registro de usuarios.
Operaciones CRUD.
Procesamiento de información.
Consultas a la base de datos.
Comunicación entre frontend y backend.

Utiliza diagramas Mermaid cuando ayuden a comprender la secuencia de ejecución.

11. Estado actual y aspectos pendientes

Identifica y separa claramente:

Funcionalidades completamente implementadas.
Funcionalidades parcialmente implementadas.
Funcionalidades pendientes.
Errores conocidos o problemas detectados.
Código provisional, simulado o de prueba.
Posibles mejoras técnicas.

No asumas que una funcionalidad está terminada únicamente porque existe un archivo o componente relacionado.

12. Guía para futuros desarrolladores

Incluye recomendaciones para que otro desarrollador pueda continuar el proyecto:

Dónde implementar nuevas funcionalidades.
Qué archivos modificar para realizar cambios habituales.
Cómo agregar nuevos módulos, componentes o endpoints.
Cómo modificar la estructura de la base de datos.
Qué dependencias o configuraciones deben tenerse en cuenta.
Qué convenciones sigue actualmente el proyecto.
13. Requisitos de calidad de la documentación

Cumple obligatoriamente las siguientes condiciones:

Toda la documentación debe estar basada en el código y los archivos reales del proyecto.
No inventes tecnologías, funcionalidades, tablas, relaciones, endpoints ni conexiones.
Cuando no puedas confirmar algo, indícalo expresamente como "No identificado" o "Pendiente de verificar".
Diferencia claramente entre funcionalidades implementadas, parcialmente implementadas y propuestas.
Siempre que sea posible, referencia las rutas exactas de los archivos relacionados con cada explicación.
Utiliza ejemplos concretos para explicar los procesos importantes.
Incluye diagramas Mermaid para representar la arquitectura, las relaciones de base de datos y los flujos relevantes cuando sea posible.
Utiliza lenguaje técnico, claro y explicativo, evitando descripciones demasiado genéricas.
Organiza el documento con títulos, subtítulos, tablas y listas para facilitar su lectura.
No modifiques, elimines ni reestructures ningún archivo existente del proyecto.
Resultado esperado

Crea exclusivamente el archivo DOCUMENTACION_PROYECTO.md en la raíz del proyecto.

El documento debe funcionar como una fuente central de conocimiento técnico: cualquier desarrollador que lo lea debe poder comprender qué hace el sistema, cómo está construido, cómo se comunican sus componentes, cómo funciona su base de datos y cómo continuar su desarrollo.

Al finalizar, verifica que el archivo exista, que su contenido sea coherente con el código analizado y que no contenga información sensible.

Finalmente, presenta un breve resumen de:

Qué áreas del proyecto fueron analizadas.
Qué secciones incluye la documentación.
Qué aspectos no pudieron verificarse.
Qué archivos principales se utilizaron como referencia.