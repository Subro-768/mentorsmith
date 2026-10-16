package app.mentorsmith.android.data.remote

import org.json.JSONObject
import java.io.BufferedReader
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID

/**
 * Talks to the optional sync backend.
 *
 * ## Why there is no AI key in this app
 *
 * An APK is not a secret. Anything shipped inside it — a string constant, a
 * resource, a native library — can be extracted by anyone who downloads it. So
 * this app **never holds a provider API key**. If tutor chat is wanted on
 * Android it must go through a backend that holds the key server-side and
 * answers on the user's behalf. That is the only design here that does not
 * ship a shared secret to every device.
 *
 * ## Transport
 *
 * `HttpURLConnection` rather than OkHttp/Retrofit. The whole contract is one
 * POST endpoint returning JSON, so a networking library and its transitive
 * dependencies would be a lot of shipped surface for very little.
 */
class SyncClient(
    private val baseUrlProvider: () -> String?,
    private val connectTimeoutMs: Int = 10_000,
    private val readTimeoutMs: Int = 20_000,
    /** Injectable so tests never touch the network. */
    private val transport: Transport = HttpUrlConnectionTransport(),
) {

    /** One HTTP call, isolated so tests can substitute a fake. */
    interface Transport {
        fun post(url: String, body: String): String
    }

    sealed class Result {
        data class Success(val response: SyncResponse) : Result()
        data class Failure(val message: String, val retryable: Boolean) : Result()
        /** No backend configured. The app is offline-first, so this is normal. */
        object NotConfigured : Result()
    }

    /**
     * Send queued changes and receive the server's.
     *
     * Returns [Result.NotConfigured] rather than throwing when no base URL is
     * set, because being offline is the normal state for this app.
     */
    fun sync(
        deviceId: String = defaultDeviceId(),
        since: String? = null,
        changes: List<SyncChange> = emptyList(),
    ): Result {
        val baseUrl = baseUrlProvider()?.trim()
        if (baseUrl.isNullOrEmpty()) return Result.NotConfigured

        val endpoint = baseUrl.trimEnd('/') + "/v1/sync"
        val request = SyncRequest(deviceId = deviceId, since = since, changes = changes)

        return try {
            val body = transport.post(endpoint, request.toJson().toString())
            val parsed = SyncResponse.fromJson(JSONObject(body))
            if (parsed.hasBreakingChange) {
                Result.Failure(
                    "The server requires a newer version of the app " +
                        "(needs v${parsed.minClientVersion}). Update MentorSmith.",
                    retryable = false,
                )
            } else {
                Result.Success(parsed)
            }
        } catch (error: java.net.SocketTimeoutException) {
            Result.Failure("The server did not respond in time.", retryable = true)
        } catch (error: java.net.UnknownHostException) {
            Result.Failure("Cannot reach the sync server. Check the URL and your network.", retryable = true)
        } catch (error: org.json.JSONException) {
            // A malformed body is not retryable: repeating the request returns
            // the same nonsense.
            Result.Failure("The server sent a response this app cannot read.", retryable = false)
        } catch (error: Exception) {
            Result.Failure(error.message ?: "Sync failed for an unknown reason.", retryable = true)
        }
    }

    companion object {
        /**
         * A per-install id. Random rather than derived from any hardware
         * identifier, so it carries no personal information.
         */
        fun defaultDeviceId(): String {
            val prefs = java.util.prefs.Preferences.userRoot().node("app/mentorsmith/android")
            return prefs.get("device_id", null) ?: UUID.randomUUID().toString().also {
                prefs.put("device_id", it)
            }
        }
    }
}

/** The real transport. Kept separate so tests never open a socket. */
class HttpUrlConnectionTransport(
    private val connectTimeoutMs: Int = 10_000,
    private val readTimeoutMs: Int = 20_000,
) : SyncClient.Transport {

    override fun post(url: String, body: String): String {
        val connection = URL(url).openConnection() as HttpURLConnection
        return try {
            connection.requestMethod = "POST"
            connection.connectTimeout = connectTimeoutMs
            connection.readTimeout = readTimeoutMs
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json")
            // No Authorization header: the app holds no credential, by design.
            connection.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }

            val status = connection.responseCode
            if (status !in 200..299) {
                val detail = connection.errorStream?.bufferedReader()?.use(BufferedReader::readText).orEmpty()
                throw SyncHttpException(status, detail)
            }
            connection.inputStream.bufferedReader().use(BufferedReader::readText)
        } finally {
            connection.disconnect()
        }
    }
}

class SyncHttpException(val status: Int, val detail: String) : Exception("HTTP $status: $detail")