#include "SampleGameScene.h"

void SampleGameScene::Initialize() {
	// レベルデータの読み込み (Resources/levels/testScene.json を想定)
	levelData_.reset(LevelLoader::LoadFile("testScene"));
	
	if (levelData_) {
		// 読み込んだデータに基づき、エンジンのオブジェクトを生成
		CreateObjects(levelData_->objects);
	}
}

void SampleGameScene::CreateObjects(const std::vector<LevelData::ObjectData>& data) {
	for (const auto& objData : data) {
		// MESHタイプの場合のみ、エンジンの3Dオブジェクトをインスタンス化
		if (objData.type == "MESH") {
			std::unique_ptr<Object3d> newObj = std::make_unique<Object3d>();
			newObj->Initialize();
			
			// モデルの設定 (ModelManager等で事前にロードされている必要がある)
			newObj->SetModel(objData.fileName);
			
			// ローダーで変換済みのトランスフォームを適用
			newObj->SetTranslate(objData.translation);
			newObj->SetRotation(objData.rotation);
			newObj->SetScale(objData.scaling);
			
			// リストに追加
			objects_.push_back(std::move(newObj));
		}
		
		// 子要素が存在する場合は再帰的に処理
		if (!objData.children.empty()) {
			CreateObjects(objData.children);
		}
	}
}

void SampleGameScene::Update() {
	// 全オブジェクトの更新
	for (auto& obj : objects_) {
		obj->Update();
	}
}

void SampleGameScene::Draw() {
	// 全オブジェクトの描画
	for (auto& obj : objects_) {
		obj->Draw();
	}
}

void SampleGameScene::Finalize() {
	// リソースの解放
	objects_.clear();
	levelData_.reset();
}
