// Exercise the generated Objective-C callback with separate host and guest objects.
#import <Foundation/Foundation.h>
#include <stdio.h>

@interface UIApplicationSceneSettings : NSObject <NSMutableCopying>
@property(nonatomic) BOOL foreground;
@property(nonatomic) NSUInteger deactivationReasons;
@property(nonatomic) NSInteger interfaceOrientation, deviceOrientation, userInterfaceStyle;
@property(nonatomic, copy) NSString *persistenceIdentifier;
@end
@compatibility_alias UIMutableApplicationSceneSettings UIApplicationSceneSettings;

@implementation UIApplicationSceneSettings
- (id)mutableCopyWithZone:(NSZone *)zone {
    UIApplicationSceneSettings *copy = [[self.class allocWithZone:zone] init];
    copy.foreground = self.foreground;
    copy.deactivationReasons = self.deactivationReasons;
    copy.interfaceOrientation = self.interfaceOrientation;
    copy.deviceOrientation = self.deviceOrientation;
    copy.userInterfaceStyle = self.userInterfaceStyle;
    copy.persistenceIdentifier = self.persistenceIdentifier;
    return copy;
}
@end

@interface FBSSceneSettingsDiff : NSObject
@property(nonatomic, strong) UIApplicationSceneSettings *oldHost, *updatedHost;
@end
@implementation FBSSceneSettingsDiff
- (UIMutableApplicationSceneSettings *)settingsByApplyingToMutableCopyOfSettings:(UIApplicationSceneSettings *)input {
    return input == self.oldHost ? [self.updatedHost mutableCopy] : nil;
}
@end

@interface UIApplicationSceneTransitionContext : NSObject <NSCopying>
@property(nonatomic, copy) NSSet *actions;
@end
@implementation UIApplicationSceneTransitionContext
- (id)copyWithZone:(NSZone *)zone {
    UIApplicationSceneTransitionContext *copy = [[self.class allocWithZone:zone] init];
    copy.actions = self.actions;
    return copy;
}
@end

@interface UIScene : NSObject
@property(nonatomic, strong) UIScene *window, *windowScene, *scene;
@property(nonatomic, strong) UIApplicationSceneSettings *settings;
@end
@implementation UIScene
@end

@interface SceneController : NSObject
@property(nonatomic) BOOL scarletNativeFullscreenSlot, isAppTerminationCleanUpCalled, isAppRunning;
@property(nonatomic, strong) UIScene *viewIfLoaded, *presenter;
@property(nonatomic, weak) SceneController *delegate;
@property(nonatomic, strong) UIApplicationSceneSettings *received;
@property(nonatomic, strong) UIApplicationSceneTransitionContext *receivedContext;
@end
@implementation SceneController
- (void)appTerminationCleanUp { self.isAppTerminationCleanUpCalled = YES; }
- (void)appSceneVC:(SceneController *)vc didUpdateFromSettings:(UIApplicationSceneSettings *)settings
 transitionContext:(UIApplicationSceneTransitionContext *)context lifecycleActionType:(uint32_t)actionType {
    self.received = settings;
    self.receivedContext = context;
}
#include "SceneCallback.inc"
@end

#define CHECK(condition, message) do { \
    if (!(condition)) { fprintf(stderr, "%s\n", message); return 1; } \
} while (0)

int main(void) {
    @autoreleasepool {
        UIScene *hostScene = [UIScene new];
        FBSSceneSettingsDiff *diff = [FBSSceneSettingsDiff new];
        diff.oldHost = [UIApplicationSceneSettings new];
        diff.oldHost.persistenceIdentifier = @"host";
        UIApplicationSceneTransitionContext *context = [UIApplicationSceneTransitionContext new];
        context.actions = [NSSet setWithObject:@"host action"];
        NSArray *fields = @[@"foreground", @"deactivationReasons", @"interfaceOrientation",
                            @"deviceOrientation", @"userInterfaceStyle"];
        NSMutableArray<SceneController *> *guests = [NSMutableArray new];
        for (NSString *identifier in @[@"guest-A", @"guest-B"]) {
            SceneController *guest = [SceneController new];
            guest.delegate = guest;
            guest.scarletNativeFullscreenSlot = YES;
            guest.isAppRunning = YES;
            guest.viewIfLoaded = [UIScene new];
            guest.viewIfLoaded.window = [UIScene new];
            guest.viewIfLoaded.window.windowScene = hostScene;
            guest.presenter = [UIScene new];
            guest.presenter.scene = [UIScene new];
            guest.presenter.scene.settings = [UIApplicationSceneSettings new];
            guest.presenter.scene.settings.persistenceIdentifier = identifier;
            [guests addObject:guest];
        }
        for (NSUInteger mask = 0; mask < (1u << fields.count); mask++) {
            diff.updatedHost = [diff.oldHost mutableCopy];
            for (NSUInteger i = 0; i < fields.count; i++) {
                if (mask & (1u << i)) [diff.updatedHost setValue:@1 forKey:fields[i]];
            }
            for (SceneController *guest in guests) {
                UIApplicationSceneSettings *original = guest.presenter.scene.settings;
                NSInteger sentinel = guest == guests.firstObject ? 2 : 3;
                for (NSString *key in fields) [original setValue:@(sentinel) forKey:key];
                [guest _performActionsForUIScene:hostScene withUpdatedFBSScene:nil settingsDiff:diff
                                      fromSettings:diff.oldHost transitionContext:context lifecycleActionType:2];
                CHECK([guest.received.persistenceIdentifier isEqual:original.persistenceIdentifier],
                      "guest identity replaced");
                CHECK(guest.received != original && guest.receivedContext != context &&
                      guest.receivedContext && !guest.receivedContext.actions && context.actions.count == 1,
                      "input or transition context mutated");
                for (NSUInteger i = 0; i < fields.count; i++) {
                    NSNumber *expected = (mask & (1u << i)) ? @1 : [original valueForKey:fields[i]];
                    CHECK([[guest.received valueForKey:fields[i]] isEqual:expected],
                          "host field escaped its delta");
                }
                CHECK(original.deviceOrientation == sentinel, "guest input mutated");
            }
        }
        SceneController *guest = guests.firstObject;
        guest.received = nil;
        [guest _performActionsForUIScene:[UIScene new] withUpdatedFBSScene:nil settingsDiff:diff
                             fromSettings:diff.oldHost transitionContext:context lifecycleActionType:0];
        CHECK(!guest.received, "foreign host delivered an update");
        guest.isAppRunning = NO;
        [guest _performActionsForUIScene:hostScene withUpdatedFBSScene:nil settingsDiff:diff
                             fromSettings:diff.oldHost transitionContext:context lifecycleActionType:0];
        CHECK(guest.isAppTerminationCleanUpCalled && !guest.received, "dead guest received an update");
        guest = guests.lastObject;
        guest.received = nil;
        guest.presenter.scene = nil;
        [guest _performActionsForUIScene:hostScene withUpdatedFBSScene:nil settingsDiff:diff
                             fromSettings:diff.oldHost transitionContext:context lifecycleActionType:0];
        CHECK(!guest.received, "missing guest fell back to host settings");
        guest.scarletNativeFullscreenSlot = NO;
        [guest _performActionsForUIScene:hostScene withUpdatedFBSScene:nil settingsDiff:diff
                             fromSettings:diff.oldHost transitionContext:context lifecycleActionType:0];
        CHECK([guest.received.persistenceIdentifier isEqual:@"host"], "legacy forwarding changed");
    }
    return 0;
}
