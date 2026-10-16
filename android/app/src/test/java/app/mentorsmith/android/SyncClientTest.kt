package app.mentorsmith.android

import app.mentorsmith.android.data.remote.ConflictRecord
import app.mentorsmith.android.data.remote.EntityType
import app.mentorsmith.android.data.remote.SyncChange
import app.mentorsmith.android.data.remote.SyncClient
import app.mentorsmith.android.data.remote.SyncRequest
import app.mentorsmith.android.data.remote.SyncResponse
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Sync client behaviour.
 *
 * No test opens a socket: the transport is injected, so the whole suite runs
 * offline and deterministically.
 */
class SyncClientTest {

    /** Records what was sent and replies with a scripted body. */
    private class FakeTransport(
        private val responseBody: String,
        private val error: Exception? = null,
    ) : SyncClient.Transport {
        var lastUrl: String? = null
        var lastBody: String? = null

        override fun post(url: String, body: String): String {
            lastUrl = url
            lastBody = body
            error?.let { throw it }
            return responseBody
        }
    }

    private val successBody = """
        {
          "server_time": "2026-10-16T00:00:00+00:00",
          "min_client_version": 1,
          "accepted": [{"client_id": "abc"}],
          "server_changes": [],
          "conflicts": []
        }
    """.trimIndent()

    @Test
    fun `no configured endpoint reports offline rather than failing`() {
        val client = SyncClient(baseUrlProvider = { null })
        assertEquals(SyncClient.Result.NotConfigured, client.sync())
    }

    @Test
    fun `a blank endpoint is treated as not configured`() {
        val client = SyncClient(baseUrlProvider = { "   " })
        assertEquals(SyncClient.Result.NotConfigured, client.sync())
    }

    @Test
    fun `a successful response is parsed`() {
        val transport = FakeTransport(successBody)
        val client = SyncClient({ "http://localhost:8000" }, transport = transport)
        val result = client.sync(changes = listOf(
            SyncChange("abc", EntityType.EXERCISE_ATTEMPT, "upsert", "cpp", "now"),
        ))
        assertTrue(result is SyncClient.Result.Success)
        val response = (result as SyncClient.Result.Success).response
        assertEquals(listOf("abc"), response.accepted)
        assertFalse(response.hasBreakingChange)
    }

    @Test
    fun `the trailing slash on the base url does not double up`() {
        val transport = FakeTransport(successBody)
        val client = SyncClient({ "http://localhost:8000/" }, transport = transport)
        client.sync()
        assertEquals("http://localhost:8000/v1/sync", transport.lastUrl)
    }

    @Test
    fun `a timeout is retryable`() {
        val transport = FakeTransport("", java.net.SocketTimeoutException("slow"))
        val client = SyncClient({ "http://localhost:8000" }, transport = transport)
        val result = client.sync()
        assertTrue(result is SyncClient.Result.Failure)
        assertTrue((result as SyncClient.Result.Failure).retryable)
    }

    @Test
    fun `an unknown host is retryable`() {
        val transport = FakeTransport("", java.net.UnknownHostException("nope"))
        val client = SyncClient({ "http://nowhere.invalid" }, transport = transport)
        val result = client.sync()
        assertTrue(result is SyncClient.Result.Failure)
        assertTrue((result as SyncClient.Result.Failure).retryable)
    }

    @Test
    fun `a malformed body is not retryable`() {
        val transport = FakeTransport("this is not json")
        val client = SyncClient({ "http://localhost:8000" }, transport = transport)
        val result = client.sync()
        assertTrue(result is SyncClient.Result.Failure)
        assertFalse((result as SyncClient.Result.Failure).retryable)
    }

    @Test
    fun `a server demanding a newer client is refused`() {
        val body = """{"server_time":"now","min_client_version":99,"accepted":[]}"""
        val transport = FakeTransport(body)
        val client = SyncClient({ "http://localhost:8000" }, transport = transport)
        val result = client.sync()
        assertTrue(result is SyncClient.Result.Failure)
        assertFalse((result as SyncClient.Result.Failure).retryable)
    }

    @Test
    fun `conflicts are surfaced, never silently resolved`() {
        val body = """
            {"server_time":"now","min_client_version":1,
             "accepted":[],
             "conflicts":[{"client_id":"x","entity_type":"exercise_attempt",
                           "language":"cpp","client_value":"a","server_value":"b",
                           "reason":"both changed"}]}
        """.trimIndent()
        val transport = FakeTransport(body)
        val client = SyncClient({ "http://localhost:8000" }, transport = transport)
        val result = client.sync()
        assertTrue(result is SyncClient.Result.Success)
        val conflicts = (result as SyncClient.Result.Success).response.conflicts
        assertEquals(1, conflicts.size)
        assertEquals("both changed", conflicts.first().reason)
        assertEquals("a", conflicts.first().clientValue)
        assertEquals("b", conflicts.first().serverValue)
    }

    @Test
    fun `the request carries an idempotency key per change`() {
        val transport = FakeTransport(successBody)
        val client = SyncClient({ "http://localhost:8000" }, transport = transport)
        client.sync(
            deviceId = "device-1",
            changes = listOf(SyncChange("unique-1", EntityType.REVIEW, "upsert", "python", "now")),
        )
        val body = JSONObject(transport.lastBody!!)
        assertEquals("device-1", body.getString("device_id"))
        val change = body.getJSONArray("changes").getJSONObject(0)
        assertEquals("unique-1", change.getString("client_id"))
    }

    @Test
    fun `payload values survive the round trip`() {
        val change = SyncChange(
            clientId = "c1",
            entityType = EntityType.LESSON_PROGRESS,
            operation = "upsert",
            language = "python",
            updatedAt = "2026-10-16T00:00:00+00:00",
            payload = mapOf("lesson_id" to "01-variables-and-types", "completed_at" to "now"),
        )
        val round = SyncChange.fromJson(JSONObject(change.toJson().toString()))
        assertEquals("01-variables-and-types", round.payload["lesson_id"])
        assertEquals("now", round.payload["completed_at"])
        assertEquals("python", round.language)
    }

    @Test
    fun `an unknown extra field from a newer server is ignored`() {
        val body = """
            {"server_time":"now","min_client_version":1,"accepted":[],
             "something_new":{"a":1},"server_changes":[],"conflicts":[]}
        """.trimIndent()
        val parsed = SyncResponse.fromJson(JSONObject(body))
        assertTrue(parsed.accepted.isEmpty())
    }

    @Test
    fun `no credential is ever attached to the request`() {
        // The client has no field for one, which is the point: an APK is not a
        // secret store. This test documents that invariant.
        val fields = SyncClient::class.java.declaredFields.map { it.name }
        assertFalse(fields.any { it.contains("key", ignoreCase = true) })
        assertFalse(fields.any { it.contains("token", ignoreCase = true) })
        assertFalse(fields.any { it.contains("auth", ignoreCase = true) })
    }
}