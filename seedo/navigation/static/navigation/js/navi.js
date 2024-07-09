var map;
var markers = [];
var polyline;
var currentWaypointIndex = 0;
var waypoints = [];

function initMap() {
  map = new Tmapv2.Map("map", {
    center: new Tmapv2.LatLng(37.5665, 126.978),
    zoom: 13,
    httpsMode: true,
  });
  // 현재 위치 가져오기
  getCurrentLocation();

  // 5초마다 현재 위치 업데이트
  setInterval(function () {
    getCurrentLocation();
    console.log("현재 위치 업데이트");
  }, 5000);

  map.addListener("click", function (event) {
    addMarker(event.latLng);
  });

  map.addListener("touchstart", function (event) {
    addMarker(event.latLng);
  });
}
function getCurrentLocation() {
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(successCallback, errorCallback, {
      enableHighAccuracy: true,
      maximumAge: 0,
      timeout: 5000,
    });
  } else {
    alert("Geolocation is not supported by this browser.");
  }
}

function successCallback(position) {
  var lat = position.coords.latitude;
  var lng = position.coords.longitude;
  var currentLocation = new Tmapv2.LatLng(lat, lng);

  // 현재 위치 마커 초기화 또는 위치 업데이트
  if (!markers.currentLocationMarker) {
    markers.currentLocationMarker = new Tmapv2.Marker({
      position: currentLocation,
      map: map, // 반드시 map 옵션을 설정하여 지도에 연결
      title: "현재 위치",
    });
  } else {
    markers.currentLocationMarker.setPosition(currentLocation);
  }

  map.panTo(currentLocation); // 지도를 현재 위치로 이동
}
function displayRoute(directionsData) {
  if (polyline) {
    polyline.setMap(null);
  }

  var features = directionsData.features;
  var pathCoordinates = [];
  var points = [];
  waypoints = [];

  features.forEach(function (feature) {
    if (feature.geometry.type === "Point") {
      var pointCoordinates = feature.geometry.coordinates;
      var point = new Tmapv2.LatLng(pointCoordinates[1], pointCoordinates[0]);
      points.push(point);
      waypoints.push(point); // 안내 지점 추가
    } else if (feature.geometry.type === "LineString") {
      var lineCoordinates = feature.geometry.coordinates;
      lineCoordinates.forEach(function (coord) {
        var point = new Tmapv2.LatLng(coord[1], coord[0]);
        pathCoordinates.push(point);
      });
    }
  });

  polyline = new Tmapv2.Polyline({
    path: pathCoordinates,
    strokeColor: "#FF0000",
    strokeWeight: 3,
    map: map,
  });

  var bounds = new Tmapv2.LatLngBounds();
  points.forEach(function (point) {
    bounds.extend(point);
  });
  map.fitBounds(bounds);

  var routeInfoContainer = document.getElementById("route-info");
  routeInfoContainer.innerHTML = ""; // 기존 내용 초기화

  features.forEach(function (feature, index) {
    if (index === currentWaypointIndex && feature.properties.description.includes("이동")) {
      alert("다음 안내 지점: " + feature.properties.description);
    }

    if (feature.properties.description.includes("이동")) {
      var info = document.createElement("div");
      info.classList.add("route-info-item");
      info.innerHTML = `<p>${feature.properties.description}</p>`;
      routeInfoContainer.appendChild(info);
    }
  });
}

function checkRoute(currentLocation) {
  if (!markers.currentLocationMarker) {
    console.error("현재 위치 마커가 정의되지 않았습니다.");
    return;
  }

  if (currentWaypointIndex < waypoints.length) {
    var nextWaypoint = waypoints[currentWaypointIndex];
    var distance = getDistance(currentLocation, nextWaypoint);

    if (distance < 50) {
      updateRouteInfo();
      currentWaypointIndex++;
    }
  } else {
    alert("경로를 완료했습니다.");
  }

  if (!isOnRoute(currentLocation)) {
    alert("경로를 벗어났습니다.");
  }
}

function errorCallback(error) {
  console.error("Error getting GPS position: " + error.message);
}

function addMarker(location) {
  if (markers.length >= 2) {
    markers.forEach(function (marker) {
      marker.setMap(null);
    });
    markers = [];
  }

  var marker = new Tmapv2.Marker({
    position: location,
    map: map,
  });

  markers.push(marker);

  // 마커 위치를 입력란에 표시
  if (markers.length === 1) {
    document.getElementById("startLat").value = location.lat();
    document.getElementById("startLng").value = location.lng();
  } else if (markers.length === 2) {
    document.getElementById("endLat").value = location.lat();
    document.getElementById("endLng").value = location.lng();
  }
}

function findRoute() {
  if (Object.keys(markers).length < 2) {
    console.error("출발지와 도착지를 모두 지정해주세요.");
    return;
  }

  var startLocation = markers[0].getPosition();
  var endLocation = markers[1].getPosition();
  sendLocations(startLocation, endLocation);

  // 5초마다 현재 위치 업데이트
  setInterval(function () {
    getCurrentLocation();
    console.log("현위치업데이트");
  }, 5000); // 매 5초마다 위치 업데이트

  // 경로 체크
  setInterval(function () {
    console.log("check");
    checkRoute(markers.currentLocationMarker.getPosition());
  }, 10000); // 매 10초마다 경로 체크
}

function sendLocations(startLocation, endLocation) {
  var csrftoken = getCookie("csrftoken");
  var data = {
    start_location: [startLocation.lng(), startLocation.lat()],
    end_location: [endLocation.lng(), endLocation.lat()],
  };
  console.log(JSON.stringify(data));
  fetch("/nav/location/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrftoken,
    },
    body: JSON.stringify(data),
  })
    .then((response) => {
      if (!response.ok) {
        throw new Error("네트워크 응답이 올바르지 않습니다");
      }
      return response.json();
    })
    .then((data) => {
      displayRoute(data);
    })
    .catch((error) => console.error("데이터를 가져오는 중 오류 발생:", error));
}

function updateCurrentLocationMarker(location) {
  if (!markers.currentLocationMarker) {
    markers.currentLocationMarker = new Tmapv2.Marker({
      position: location,
      map: map,
      title: "현재 위치",
    });
  } else {
    markers.currentLocationMarker.setPosition(location);
  }
  // 지도를 현재 위치로 이동
  map.panTo(location);
}

function updateRouteInfo(features) {
  var routeInfoContainer = document.getElementById("route-info");
  routeInfoContainer.innerHTML = "";

  var nextDescription = features[currentWaypointIndex].properties.description;

  var info = document.createElement("div");
  info.classList.add("route-info-item");
  info.innerHTML = `<p>다음 안내: ${nextDescription}</p>`;
  routeInfoContainer.appendChild(info);
}

function isOnRoute(currentLocation) {
  if (waypoints.length === 0) {
    console.warn("경로가 정의되지 않았습니다.");
    return false;
  }

  var toleranceDistance = 50;

  for (var i = 0; i < waypoints.length; i++) {
    var waypoint = waypoints[i];
    var distance = getDistance(currentLocation, waypoint);

    if (distance <= toleranceDistance) {
      return true; // 현재 위치가 경로상에 있는 경우
    }
  }

  return false; // 현재 위치가 경로상에 없는 경우
}

// gpt한테 물어봄 해버시늄??처음들어봄
function getDistance(location1, location2) {
  // 두 위치 사이의 거리 계산 로직을 구현합니다.
  // 예를 들어, 두 지점의 위도 경도를 사용하여 실제 거리를 계산하는 방식을 적용할 수 있습니다.
  // 여기서는 간단히 거리를 반환하도록 하겠습니다.
  var lat1 = location1.lat();
  var lng1 = location1.lng();
  var lat2 = location2.lat();
  var lng2 = location2.lng();

  // 헤버시늄 공식(Haversine formula)을 사용하여 두 지점 사이의 거리를 계산합니다.
  var radLat1 = (Math.PI * lat1) / 180;
  var radLat2 = (Math.PI * lat2) / 180;
  var theta = lng1 - lng2;
  var radTheta = (Math.PI * theta) / 180;
  var dist = Math.sin(radLat1) * Math.sin(radLat2) + Math.cos(radLat1) * Math.cos(radLat2) * Math.cos(radTheta);
  dist = Math.acos(dist);
  dist = (dist * 180) / Math.PI;
  dist = dist * 60 * 1.1515;
  dist = dist * 1.609344 * 1000; // 단위를 미터로 변환

  return dist; // 거리를 미터 단위로 반환
}

function getCookie(name) {
  var cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    var cookies = document.cookie.split(";");
    for (var i = 0; i < cookies.length; i++) {
      var cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === name + "=") {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

document.addEventListener("DOMContentLoaded", function () {
  initMap();
});

$("#btn_select").click(function () {
  var searchKeyword = $("#searchKeyword").val();
  var headers = {};
  headers["appKey"] = "po8JlsJs5W18L7GArJBDK5drZocbgJ116JTpWVN3";

  $.ajax({
    method: "GET",
    headers: headers,
    url: "https://apis.openapi.sk.com/tmap/pois?version=1&format=json&callback=result",
    async: false,
    data: {
      searchKeyword: searchKeyword,
      resCoordType: "EPSG3857",
      reqCoordType: "WGS84GEO",
      count: 10,
    },
    success: function (response) {
      var resultpoisData = response.searchPoiInfo.pois.poi;
      if (markers.length > 0) {
        for (var i in markers) {
          markers[i].setMap(null);
        }
      }
      var innerHtml = "";
      var positionBounds = new Tmapv2.LatLngBounds();

      for (var k in resultpoisData) {
        var noorLat = Number(resultpoisData[k].noorLat);
        var noorLon = Number(resultpoisData[k].noorLon);
        var name = resultpoisData[k].name;
        var pointCng = new Tmapv2.Point(noorLon, noorLat);
        var projectionCng = new Tmapv2.Projection.convertEPSG3857ToWGS84GEO(pointCng);
        var lat = projectionCng._lat;
        var lon = projectionCng._lng;
        var markerPosition = new Tmapv2.LatLng(lat, lon);

        var marker = new Tmapv2.Marker({
          position: markerPosition,
          //icon: "http://tmapapi.sktelecom.com/upload/tmap/marker/pin_b_m_" + k + ".png",
          iconSize: new Tmapv2.Size(24, 38),
          title: name,
          map: map,
        });

        innerHtml += "<li onclick='setDestination(" + lat + "," + lon + ")'><span>" + name + "</span></li>";

        markers.push(marker);
        positionBounds.extend(markerPosition);
      }

      $("#searchResult").html(innerHtml);
      map.panToBounds(positionBounds);
      map.zoomOut();
    },
    error: function (request, status, error) {
      console.log("code:" + request.status + "\n" + "message:" + request.responseText + "\n" + "error:" + error);
    },
  });
});

function setDestination(lat, lon) {
  if (!document.getElementById("startLat").value) {
    document.getElementById("startLat").value = lat;
    document.getElementById("startLng").value = lon;
  } else if (!document.getElementById("endLat").value) {
    document.getElementById("endLat").value = lat;
    document.getElementById("endLng").value = lon;
  }
}
