package org.thp.thehive.connector.misp.services

import org.thp.scalligraph.auth.AuthContext
import org.thp.scalligraph.models.{Database, DummyUserSrv, Entity}
import org.thp.scalligraph.traversal.Graph
import org.thp.thehive.TestAppBuilder
import org.thp.thehive.models.{Observable, Permissions, Tag}
import org.thp.thehive.services.ObservableOps._
import org.thp.thehive.services.{ObservableSrv, TagSrv}
import play.api.test.PlaySpecification

import scala.concurrent.ExecutionContext

class MispExportSrvTest(implicit ec: ExecutionContext) extends PlaySpecification with TestAppBuilder {
  sequential

  implicit val authContext: AuthContext =
    DummyUserSrv(userId = "certuser@thehive.local", organisation = "cert", permissions = Permissions.all).authContext

  "MispExportSrv" should {
    "export observable tags with colour" in testApp { app =>
      val observableSrv = app[ObservableSrv]
      val tagSrv        = app[TagSrv]
      val mispExportSrv = app[MispExportSrv]

      app[Database].tryTransaction { implicit graph =>
        // Setup tags
        val tagName = "test:tag=1"
        val tagColour = "#FF0000"
        val tag = tagSrv.getOrCreate(tagName).get
        tagSrv.update(tag, tag.copy(colour = tagColour))

        // Setup observable
        val obs = Observable(None, 2, ioc = true, sighted = false, None, "domain", Seq(tagName))
        val createdObs = observableSrv.create(obs, "example.com").get

        // Fetch rich observable to simulate service call
        val richObs = observableSrv.get(createdObs).richObservable.head

        // Test
        val attribute = mispExportSrv.observableToAttribute(richObs, exportTags = true)

        attribute must beSome
        val tags = attribute.get.tags
        tags must contain((t: org.thp.misp.dto.Tag) => t.name == tagName && t.colour == Some(tagColour))
      }
    }
  }
}
