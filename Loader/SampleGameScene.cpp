#include "SampleGameScene.h"

void SampleGameScene::Initialize() {
	levelData_.reset(LevelLoader::LoadFile("testScene"));

	if (!levelData_) {
		return;
	}

	CreateObjects(levelData_->objects);
	CreatePlayerSpawns(levelData_->players);
	CreateEnemySpawns(levelData_->enemies);
}

void SampleGameScene::CreateObjects(const std::vector<LevelData::ObjectData>& data) {
	for (const auto& objData : data) {
		if (objData.type == "MESH") {
			std::unique_ptr<Object3d> newObj = std::make_unique<Object3d>();
			newObj->Initialize();
			newObj->SetModel(objData.fileName);
			newObj->SetTranslate(objData.translation);
			newObj->SetRotation(objData.rotation);
			newObj->SetScale(objData.scaling);
			objects_.push_back(std::move(newObj));
		}

		if (!objData.children.empty()) {
			CreateObjects(objData.children);
		}
	}
}

void SampleGameScene::CreatePlayerSpawns(const std::vector<LevelData::PlayerSpawnData>& data) {
	for (const auto& spawnData : data) {
		// Sample: place a sphere at each player spawn.
		std::unique_ptr<Object3d> marker = std::make_unique<Object3d>();
		marker->Initialize();
		marker->SetModel("sphere");
		marker->SetTranslate(spawnData.translation);
		marker->SetRotation(spawnData.rotation);

		// Make it a little smaller so the marker is easy to distinguish.
		marker->SetScale({ 0.25f, 0.25f, 0.25f });

		playerSpawnObjects_.push_back(std::move(marker));
	}
}

void SampleGameScene::CreateEnemySpawns(const std::vector<LevelData::EnemySpawnData>& data) {
	for (const auto& spawnData : data) {
		std::unique_ptr<Object3d> marker = std::make_unique<Object3d>();
		marker->Initialize();
		marker->SetModel("sphere");
		marker->SetTranslate(spawnData.translation);
		marker->SetRotation(spawnData.rotation);
		marker->SetScale({ 0.2f, 0.2f, 0.2f });
		playerSpawnObjects_.push_back(std::move(marker));
	}
}

void SampleGameScene::Update() {
	for (auto& obj : objects_) {
		obj->Update();
	}

	for (auto& obj : playerSpawnObjects_) {
		obj->Update();
	}
}

void SampleGameScene::Draw() {
	for (auto& obj : objects_) {
		obj->Draw();
	}

	for (auto& obj : playerSpawnObjects_) {
		obj->Draw();
	}
}

void SampleGameScene::Finalize() {
	objects_.clear();
	playerSpawnObjects_.clear();
	levelData_.reset();
}
