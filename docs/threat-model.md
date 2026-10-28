# Threat Model

## Scope

The system is a local three-party demonstration. The coordinator performs face detection and embedding extraction. Each party stores one Shamir share in its own SQLite database. MPyC performs the authentication comparison among three party processes.

## Assumptions

- At most one party is passively curious; MPyC's three-party configuration uses threshold 2.
- Party API tokens are protected and are not logged.
- Model files are downloaded from the documented OpenCV Zoo sources and verified before use.
- A face embedding is not evidence of liveness or resistance to presentation attacks.

## Out of scope

- Malicious-party security, collusion of two parties, compromised host kernels, and physical camera tampering.
- Accuracy claims without a representative genuine/impostor dataset.
- Independent infrastructure: localhost processes do not provide physical fault isolation.

## Trust boundaries

The coordinator temporarily handles raw frames and query embeddings. Party services receive control requests and persist shares. The current local MPyC launcher uses a temporary query file readable by local party processes; a remote deployment requires authenticated private input channels.

## Fail-closed behavior

Missing, malformed, inconsistent, or unavailable shares cause authentication failure. Partial enrollment is rolled back where possible. Rollback failure is reported as requiring manual repair.